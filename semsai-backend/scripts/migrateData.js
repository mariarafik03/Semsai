
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import fs from 'fs';
import csv from 'csv-parser';
import path from 'path'; // Corrected import
import { fileURLToPath } from 'url';

// Import Models
import Compound from '../models/Compound.js';
import Developer from '../models/Developer.js';
import Unit from '../models/Unit.js';
import Residential from '../models/Residential.js';
import Location from '../models/Location.js';
import Media from '../models/Media.js';
import Payment from '../models/Payment.js';

// Setup environment
dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CSV_FILE_PATH = 'e:/StudioProjects/SemsAi/SemsAi/nawy_enriched.csv';

const connectDB = async () => {
    try {
        await mongoose.connect(process.env.MONGO_URI || 'mongodb://localhost:27017/semsai'); // Fallback if env missing
        console.log('MongoDB Connected');
    } catch (err) {
        console.error('MongoDB Connection Error:', err);
        process.exit(1);
    }
};

const cleanPrice = (priceStr) => {
    if (!priceStr) return 0;
    return parseFloat(priceStr.replace(/[^0-9.]/g, ''));
};

const parseDurationMonths = (val, unit) => {
    const num = parseFloat(val);
    if (isNaN(num)) return 0;
    if (unit && unit.toLowerCase().includes('year')) return num * 12;
    return num;
};

const extractDeveloper = (description) => {
    if (!description) return "Unknown Developer";
    const match = description.match(/by\s+(.*?)(?:\.|$)/);
    return match ? match[1].trim() : "Unknown Developer";
};

const migrate = async () => {
    await connectDB();

    const results = [];
    
    // Create a stream
    fs.createReadStream(CSV_FILE_PATH)
        .pipe(csv())
        .on('data', (data) => results.push(data))
        .on('end', async () => {
            console.log(`Parsed ${results.length} rows. Starting migration...`);

            // Cache for Compounds and Developers to avoid redundant DB calls
            const compoundsCache = {}; 
            const developersCache = {};

            // Batch processing could be better, but we'll do sequential for safety first
            for (const row of results) {
                try {
                    // 1. Extract Basic Data
                    // Map headers based on inspection
                    // "name": "Type, Compound Name" -> "Apartment, Kayan-Phase 1"
                    const nameParts = row['name'] ? row['name'].split(',') : ['Unknown', 'Unknown'];
                    const unitType = nameParts[0].trim();
                     // Join the rest in case compound name has commas
                    const compoundName = nameParts.slice(1).join(',').trim() || "Unknown Compound";
                    
                    const locationArea = row['area']; // "Northern Expansion"
                    const description = row['sc-4b9910fd-0'];
                    const developerName = extractDeveloper(description);
                    
                    const unitArea = parseFloat(row['value']); // 125
                    const bedrooms = parseFloat(row['value 2']); // 3
                    const bathrooms = parseFloat(row['value 3']); // 2
                    
                    const price = cleanPrice(row['price']);
                    
                    // Payment parsing
                    // "down-payment": "410,118 EGP quarterly"
                    // "down-payment 3": "4"
                    // "down-payment 4": "Years"
                    const installmentStr = row['down-payment'];
                    const installmentAmount = cleanPrice(installmentStr);
                    // Naive monthly calculation if quarterly
                    let monthlyInstallment = installmentAmount;
                    if (installmentStr && installmentStr.toLowerCase().includes('quarterly')) {
                        monthlyInstallment = installmentAmount / 3;
                    }
                    
                    const durationVal = row['down-payment 3'];
                    const durationUnit = row['down-payment 4'];
                    const months = parseDurationMonths(durationVal, durationUnit);


                    // 2. Handle Developer
                    let devId;
                    if (developersCache[developerName]) {
                        devId = developersCache[developerName];
                    } else {
                        let dev = await Developer.findOne({ dev_name: developerName });
                        if (!dev) {
                            dev = await Developer.create({ dev_name: developerName });
                            console.log(`Created Developer: ${developerName}`);
                        }
                        devId = dev._id;
                        developersCache[developerName] = devId;
                    }

                    const amenitiesStr = (row['amenities_extracted'] || '').toLowerCase();
                    const parsedAmenities = {
                        clubhouse: amenitiesStr.includes('clubhouse'),
                        gym: amenitiesStr.includes('gym'),
                        cafes: amenitiesStr.includes('cafe'),
                        restaurants: amenitiesStr.includes('restaurant'),
                        parks: amenitiesStr.includes('park'),
                        commercial_strip: amenitiesStr.includes('commercial strip'),
                        food_court: amenitiesStr.includes('food court'),
                        outdoor_pools: amenitiesStr.includes('pool'),
                        children_play_area: amenitiesStr.includes('children') || amenitiesStr.includes('play area'),
                        barbecue_area: amenitiesStr.includes('barbecue'),
                        bicycle_lanes: amenitiesStr.includes('bike') || amenitiesStr.includes('bicycle'),
                        jogging_trail: amenitiesStr.includes('jogging') || amenitiesStr.includes('trail')
                    };

                    // 3. Handle Compound
                    let compoundId;
                    if (compoundsCache[compoundName]) {
                        compoundId = compoundsCache[compoundName];
                    } else {
                        let compound = await Compound.findOne({ name: compoundName });
                        if (!compound) {
                            compound = await Compound.create({
                                name: compoundName,
                                location: locationArea,
                                developer_id: devId,
                                description: description,
                                lat: row['lat_extracted'] || null,
                                lng: row['lng_extracted'] || null,
                                amenities: parsedAmenities,
                                is_gated: row['is_gated_extracted'] === 'Yes',
                                unit_count: row['unit_count_extracted'] || null
                            });
                            console.log(`Created Compound: ${compoundName}`);
                        } else {
                            let modified = false;
                            if (!compound.lat && row['lat_extracted']) {
                                compound.lat = row['lat_extracted'];
                                compound.lng = row['lng_extracted'];
                                modified = true;
                            }
                            if (row['is_gated_extracted']) {
                                compound.is_gated = row['is_gated_extracted'] === 'Yes';
                                modified = true;
                            }
                            if (row['unit_count_extracted']) {
                                compound.unit_count = row['unit_count_extracted'];
                                modified = true;
                            }
                            if (amenitiesStr.length > 5) {
                                compound.amenities = parsedAmenities;
                                modified = true;
                            }
                            if (modified) await compound.save();
                        }
                        compoundId = compound._id;
                        compoundsCache[compoundName] = compoundId;
                    }

                    // 4. Create Unit
                    const unit = await Unit.create({
                        compound_id: compoundId,
                        type: unitType,
                        area: unitArea,
                        price: price,
                        status: 'Available',
                        delivery_year: row['delivery_extracted'] || null,
                        finishing: row['finishing_extracted'] || 'Unknown',
                        lat: row['lat_extracted'] || null,
                        lng: row['lng_extracted'] || null,
                        amenities: row['amenities_extracted'] ? row['amenities_extracted'].split(' | ') : []
                    });

                    // 5. Create Residential Specs
                    await Residential.create({
                        unit_id: unit._id,
                        bedrooms: bedrooms,
                        bathrooms: bathrooms,
                        finishing: 'Unknown' // Not clear in CSV headers inspected
                    });

                    // 6. Create Location (Unit specific if any, otherwise skip or link)
                    // We really just have "area" which is compound level. 
                    // We can skip creating a per-unit location if it's identical to compound.
                    // But if we want geospatial queries on units, we might want it.
                    // For now, let's skip to save space unless we have lat/long.

                    // 7. Create Media
                    if (row['sc-a8a5fdb6-0 src']) {
                        await Media.create({
                            unit_id: unit._id,
                            compound_id: compoundId,
                            url: row['sc-a8a5fdb6-0 src'],
                            type: 'image'
                        });
                    }

                    // 8. Create Payment
                    if (months > 0 || monthlyInstallment > 0) {
                        await Payment.create({
                            unit_id: unit._id,
                            monthly_installment: Math.round(monthlyInstallment),
                            duration: months
                        });
                    }

                } catch (err) {
                    console.error(`Error processing row: ${err.message}`);
                    // Continue to next row
                }
            }

            console.log('Migration Complete.');
            process.exit(0);
        });
};

migrate();
