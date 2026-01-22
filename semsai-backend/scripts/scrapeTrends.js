
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import Compound from '../models/Compound.js';
import Unit from '../models/Unit.js';
import MarketMetric from '../models/MarketMetric.js';
import fetch from 'node-fetch';

dotenv.config();

const MONGO_URI = process.env.MONGO_URI || 'mongodb+srv://semsai_user:EA-xQASp73Y9_fF@cluster0.vdtyjnl.mongodb.net/semsai?retryWrites=true&w=majority&appName=Cluster0';

async function scrapeTrends() {
    console.log('Starting Price History Extraction via HTML Analysis...');
    await mongoose.connect(MONGO_URI);
    console.log('Connected to MongoDB');

    // 1. Get compounds that have units with URLs
    const compounds = await Compound.find({});
    console.log(`Found ${compounds.length} compounds to check.`);

    for (const compound of compounds) {
        // Find one unit from this compound that has a PropertyFinder URL
        const sampleUnit = await Unit.findOne({ 
            compound_id: compound._id,
            url: { $regex: /propertyfinder\.eg/ }
        });

        if (!sampleUnit) {
            console.log(`Skipping ${compound.name}: No units with URL found.`);
            continue;
        }

        console.log(`Processing ${compound.name} via URL: ${sampleUnit.url}`);

        try {
            const response = await fetch(sampleUnit.url, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html',
                }
            });

            if (!response.ok) {
                console.warn(`  - Failed to fetch page for ${compound.name}: ${response.status}`);
                continue;
            }

            const html = await response.text();
            
            // Extract __NEXT_DATA__
            const scriptMatch = html.match(/<script id="__NEXT_DATA__" type="application\/json">([\s\S]*?)<\/script>/);
            if (!scriptMatch) {
                console.warn(`  - Could not find __NEXT_DATA__ for ${compound.name}`);
                continue;
            }

            const nextData = JSON.parse(scriptMatch[1]);
            const trendsData = nextData.props?.pageProps?.priceTrendsData;

            if (trendsData && trendsData.graph) {
                // Save trends for this compound
                // Note: The trends often vary by bedroom count. PropertyFinder usually shows the trend for the current unit's bedroom count.
                // We'll store what we found.
                
                const periods = ['1Y', '2Y', '5Y'];
                for (const period of periods) {
                    const points = trendsData.graph[period];
                    if (!points || points.length === 0) continue;

                    // Group by transaction type (Sale/Rent is usually determined by the listing type)
                    // We can infer it from the URL or trendsData keys if available.
                    const transactionType = sampleUnit.url.includes('/rent/') ? 'Rent' : 'Buy';
                    const unitType = sampleUnit.type || 'Apartment';

                    const historyPoints = points.map(pt => ({
                        date: new Date(pt.date),
                        avg_price: pt.towerPrice || pt.communityPrice,
                        community_avg_price: pt.communityPrice
                    }));

                    await MarketMetric.updateOne(
                        { 
                            compound_id: compound._id, 
                            type: unitType, 
                            transaction_type: transactionType,
                            period: period // Optionally track per period, but history array usually covers it
                        },
                        {
                            $set: {
                                history: historyPoints,
                                meta: {
                                    communityName: trendsData.communityName,
                                    towerName: trendsData.towerName,
                                    bedrooms: trendsData.bedrooms
                                },
                                last_updated: new Date()
                            }
                        },
                        { upsert: true }
                    );
                }
                console.log(`  - Successfully saved trends for ${compound.name}`);
            } else {
                console.log(`  - No trends data in page for ${compound.name}`);
            }

        } catch (err) {
            console.error(`  - Error processing ${compound.name}:`, err.message);
        }

        // Delay to avoid anti-bot
        await new Promise(r => setTimeout(r, 2000));
    }

    console.log('Extraction Complete.');
    await mongoose.disconnect();
}

scrapeTrends();
