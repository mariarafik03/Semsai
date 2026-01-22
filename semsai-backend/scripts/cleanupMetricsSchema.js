
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import MarketMetric from '../models/MarketMetric.js';

dotenv.config();

const MONGO_URI = process.env.MONGO_URI || 'mongodb+srv://semsai_user:EA-xQASp73Y9_fF@cluster0.vdtyjnl.mongodb.net/semsai?retryWrites=true&w=majority&appName=Cluster0';

async function cleanupMetricsSchema() {
    console.log('Starting Final Schema Cleanup...');
    await mongoose.connect(MONGO_URI);
    console.log('Connected to MongoDB');

    // Fields to remove from the root of the document
    const fieldsToRemove = {
        avg_resale_listings: "",
        demand_growth: "",
        infrastructure_index: "",
        location_access_score: "",
        location_growth_score: "",
        rent_yield: "",
        rental_demand_score: "",
        resale_liquidity_score: "",
        location: "" // Extra redundant field noticed in some Nawy records
    };

    console.log('Unsetting redundant flat fields across all records...');
    
    // We use updateMany with $unset to remove these fields if they exist at the root
    const result = await MarketMetric.updateMany(
        {},
        { $unset: fieldsToRemove }
    );

    console.log(`Cleanup Complete. Modified ${result.modifiedCount} records.`);
    await mongoose.disconnect();
}

cleanupMetricsSchema();
