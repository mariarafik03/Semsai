
import { chromium } from 'playwright';
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import Unit from '../models/Unit.js';
import Compound from '../models/Compound.js';
import Media from '../models/Media.js';
import Payment from '../models/Payment.js';
import fs from 'fs';
import path from 'path';

dotenv.config();

const MONGO_URI = process.env.MONGO_URI || 'mongodb+srv://semsai_user:EA-xQASp73Y9_fF@cluster0.vdtyjnl.mongodb.net/semsai?retryWrites=true&w=majority&appName=Cluster0';
const PROGRESS_FILE = path.resolve('propertyfinder_progress.json');
const BASE_URL = 'https://www.propertyfinder.eg/en/search?c=1&ob=mr&page=';
const MAX_RETRIES = 3;

async function scrapePropertyFinder() {
    console.log('Starting PropertyFinder Scraper...');
    
    // Connect to MongoDB
    await mongoose.connect(MONGO_URI);
    console.log('Connected to MongoDB');

    let browser;
    let context;
    let page;
    
    // Load progress
    let startPage = 1;
    if (fs.existsSync(PROGRESS_FILE)) {
        const progress = JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf-8'));
        startPage = progress.page || 1;
        console.log(`Resuming from page ${startPage}`);
    }

    try {
        browser = await chromium.launch({ headless: false }); // Headless false to avoid immediate detection
        context = await browser.newContext({
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport: { width: 1280, height: 720 }
        });
        
        // Cache compounds to minimize DB queries
        const compoundsCache = {}; // name -> id

        for (let pageNum = startPage; pageNum <= 6500; pageNum++) {
            page = await context.newPage();
            const url = `${BASE_URL}${pageNum}`;
            console.log(`Scraping Page ${pageNum}...`);
            
            let retries = 0;
            let success = false;
            let listings = [];

            while (!success && retries < MAX_RETRIES) {
                try {
                    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
                    
                    // Extract __NEXT_DATA__
                    listings = await page.evaluate(() => {
                        const script = document.getElementById('__NEXT_DATA__');
                        if (!script) return [];
                        const data = JSON.parse(script.textContent);
                        return data.props?.pageProps?.searchResult?.listings?.map(l => l.property) || [];
                    });

                    success = true;
                } catch (e) {
                    console.error(`Error scraping page ${pageNum}:`, e.message);
                    retries++;
                    await new Promise(r => setTimeout(r, 5000));
                }
            }

            if (!success || listings.length === 0) {
                console.warn(`No listings found on page ${pageNum}, stopping or skipping.`);
                if (retries >= MAX_RETRIES) break; // Stop if persistent error
            }

            // Process Listings
            for (const prop of listings) {
                try {
                    const externalId = String(prop.id);
                    const compoundName = extractCompoundName(prop);
                    
                    // 1. Resolve Compound
                    let compoundId = compoundsCache[compoundName];
                    if (!compoundId && compoundName) {
                        // Fuzzy find or create
                        let compound = await Compound.findOne({ 
                            name: { $regex: new RegExp(`^${compoundName}$`, 'i') } 
                        });
                        
                        if (!compound) {
                            compound = await Compound.create({
                                name: compoundName,
                                propertyfinder_id: prop.location?.id, // Capture ID for trends
                                location: prop.location?.full_name,
                                lat: prop.coordinates?.lat,
                                lng: prop.coordinates?.lon,
                                description: `Imported from PropertyFinder`,
                                is_gated: false // Default
                            });
                            console.log(`Created new Compound: ${compoundName} (PF ID: ${prop.location?.id})`);
                        } else {
                             // Enrich existing compound with PF ID if missing
                             let modified = false;
                             if (!compound.propertyfinder_id && prop.location?.id) {
                                 compound.propertyfinder_id = prop.location.id;
                                 modified = true;
                             }
                             if (!compound.lat && prop.coordinates?.lat) {
                                 compound.lat = prop.coordinates.lat;
                                 compound.lng = prop.coordinates.lon;
                                 modified = true;
                             }
                             if (modified) await compound.save();
                        }
                        
                        compoundId = compound._id;
                        compoundsCache[compoundName] = compoundId;
                    }

                    if (!compoundId) {
                         // Fallback for independent units if needed, or skip
                         // console.log(`Skipping unit ${externalId} (No compound name)`);
                         continue; 
                    }

                    // 2. Upsert Unit
                    const extractedType = prop.type_id === 1 ? 'Apartment' : (prop.type_id === 3 ? 'Villa' : 'Unit');
                    const amenitiesList = prop.amenities ? prop.amenities.map(a => a.name) : [];

                    await Unit.updateOne(
                        { external_id: externalId },
                        {
                            $set: {
                                compound_id: compoundId,
                                type: extractedType,
                                price: prop.price?.value,
                                area: prop.size?.value,
                                bedrooms: prop.bedrooms,
                                bathrooms: prop.bathrooms,
                                finishing: prop.finishing_type || 'Unknown',
                                lat: prop.coordinates?.lat,
                                lng: prop.coordinates?.lon,
                                amenities: amenitiesList,
                                images: prop.images?.map(img => img.full || img.small),
                                agent: prop.agent,
                                listed_date: prop.listed_date ? new Date(prop.listed_date * 1000) : new Date(),
                                url: prop.share_url
                            }
                        },
                        { upsert: true, new: true }
                    );
                    
                    // Fetch the unit to get its _id (if it was just upserted, we need the doc)
                    const unitDoc = await Unit.findOne({ external_id: externalId });

                    if (unitDoc) {
                        // 3. Populate Media Collection
                        if (prop.images && prop.images.length > 0) {
                             // Strategy: Clear old media for this unit and re-insert to ensure sync
                             await Media.deleteMany({ unit_id: unitDoc._id });
                             const mediaDocs = prop.images.map(img => ({
                                 unit_id: unitDoc._id,
                                 compound_id: compoundId,
                                 url: img.full || img.small,
                                 type: 'image'
                             }));
                             await Media.insertMany(mediaDocs);
                        }

                        // 4. Populate Payment Collection
                        // PropertyFinder prices are usually "Total Price (Cash)" unless processed otherwise.
                        // We'll create a default "Cash" payment plan if price exists.
                        if (prop.price?.value) {
                             await Payment.deleteMany({ unit_id: unitDoc._id });
                             await Payment.create({
                                 unit_id: unitDoc._id,
                                 compound_id: compoundId,
                                 down_payment: 0,
                                 monthly_installment: 0,
                                 duration: 0,
                                 cash: true,
                                 plan_name: 'Cash'
                             });
                        }
                    }

                } catch (err) {
                    console.error(`Error processing property ${prop.id}:`, err.message);
                }
            }
            
            await page.close();

            // Save Progress
            fs.writeFileSync(PROGRESS_FILE, JSON.stringify({ page: pageNum + 1 }));

            // Human Delay
            const delay = Math.floor(Math.random() * 3000) + 2000;
            await new Promise(r => setTimeout(r, delay));
        }

    } catch (error) {
        console.error('Fatal Scraper Error:', error);
    } finally {
        if (browser) await browser.close();
        await mongoose.disconnect();
    }
}

function extractCompoundName(prop) {
    // Attempt 1: From location tree (usually index 1 or 2 is compound)
    // E.g. "Egypt > Cairo > New Cairo > The Waterway"
    // Check location_tree which is not always present in summary
    
    // Attempt 2: From full location string
    // "Apartment for sale in The Waterway, New Cairo"
    // Heuristic: Extract the part before the common district name
    
    let text = prop.location?.full_name || '';
    if (!text) return null;

    // Simple heuristic: Try to find known compound names or use the first segment
    // This is the hardest part. For now, let's try to parse "X in Y"
    // "Apartment for sale in [Compound], [City]" matches title logic sometimes
    
    // Better: prop.tower_name or prop.community_name if available in JSON
    // Inspected JSON shows 'location_tree' might be available only on detail page?
    // Let's use what we have. API response usually has 'location' object with name.
    
    // If 'community' is in location hierarchy
    if (prop.location?.name) {
        return prop.location.name; 
    }
    
    return null;
}

scrapePropertyFinder();
