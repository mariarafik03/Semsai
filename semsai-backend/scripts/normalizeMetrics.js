
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import MarketMetric from '../models/MarketMetric.js';
import Compound from '../models/Compound.js';
import Unit from '../models/Unit.js';

dotenv.config();

const MONGO_URI = process.env.MONGO_URI || 'mongodb+srv://semsai_user:EA-xQASp73Y9_fF@cluster0.vdtyjnl.mongodb.net/semsai?retryWrites=true&w=majority&appName=Cluster0';

async function normalizeMetrics() {
    console.log('Starting Data Normalization and Enrichment...');
    await mongoose.connect(MONGO_URI);
    console.log('Connected to MongoDB');

    const metrics = await MarketMetric.find({});
    console.log(`Analyzing ${metrics.length} metric records...`);

    let count = 0;
    for (const metric of metrics) {
        count++;
        if (count % 100 === 0) console.log(`  - Processed ${count}/${metrics.length} records...`);
        try {
            // 1. Sort history by date (newest first)
            let history = metric.history || [];
            history.sort((a, b) => new Date(b.date) - new Date(a.date));

            const updates = {
                calculated: {},
                last_normalized: new Date()
            };

            if (history.length > 0) {
                const latestPrice = history[0].avg_price;
                
                // 2. Calculate Annual Growth (1Y)
                const oneYearAgo = new Date();
                oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
                
                const yearAgoPoint = history.find(p => new Date(p.date) <= oneYearAgo) || history[history.length - 1];
                
                if (yearAgoPoint && yearAgoPoint.avg_price > 0) {
                    const growth = ((latestPrice - yearAgoPoint.avg_price) / yearAgoPoint.avg_price) * 100;
                    updates.calculated.annual_growth = parseFloat(growth.toFixed(2));
                }

                // 3. Rent Yield Calculation (only for 'Buy' metrics)
                if (metric.transaction_type === 'Buy') {
                    const rentMetric = await MarketMetric.findOne({
                        compound_id: metric.compound_id,
                        type: metric.type,
                        transaction_type: 'Rent'
                    });

                    if (rentMetric && rentMetric.history && rentMetric.history.length > 0) {
                        const latestRent = rentMetric.history.sort((a, b) => new Date(b.date) - new Date(a.date))[0].avg_price;
                        // Yield = (Annual Rent / Purchase Price) * 100
                        const yieldValue = ((latestRent * 12) / latestPrice) * 100;
                        updates.calculated.rent_yield = parseFloat(yieldValue.toFixed(2));
                    }
                }
            }

            // 4. Listing Count Enrichment
            const unitCount = await Unit.countDocuments({ compound_id: metric.compound_id });
            updates.calculated.available_listings = unitCount;

            // 5. Cleanup Inconsistent Nawy Fields (move to 'legacy' or nested)
            // If the document has flat fields (like demand_growth) not in schema
            const doc = metric.toObject();
            if (doc.demand_growth !== undefined || doc.rent_yield !== undefined && !updates.calculated.rent_yield) {
                updates.legacy_scores = {
                    demand_growth: doc.demand_growth,
                    rent_yield: doc.rent_yield,
                    infrastructure_index: doc.infrastructure_index,
                    location_access_score: doc.location_access_score,
                    location_growth_score: doc.location_growth_score
                };
            }

            // 6. Update document
            await MarketMetric.updateOne(
                { _id: metric._id },
                { $set: updates }
            );

            // 7. Update Parent Compound's Aggregated Stats
            if (metric.transaction_type === 'Buy' && history.length > 0) {
                const year = new Date().getFullYear();
                const latestPrice = history[0].avg_price;
                
                await Compound.updateOne(
                    { _id: metric.compound_id, "market_history.year": year },
                    { 
                        $set: { "market_history.$.avg_sale_price": latestPrice } 
                    }
                );
                
                // If year doesn't exist in market_history, push it
                const compound = await Compound.findById(metric.compound_id);
                if (compound && !compound.market_history.some(h => h.year === year)) {
                    await Compound.updateOne(
                        { _id: metric.compound_id },
                        { 
                            $push: { 
                                market_history: { 
                                    year, 
                                    avg_sale_price: latestPrice,
                                    avg_rent_price: 0,
                                    occupancy_rate: 0
                                } 
                            } 
                        }
                    );
                }
            }

        } catch (err) {
            console.error(`Error normalizing metric ${metric._id}:`, err.message);
        }
    }

    console.log('Normalization and Enrichment Complete.');
    await mongoose.disconnect();
}

normalizeMetrics();
