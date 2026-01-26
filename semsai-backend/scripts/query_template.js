
/**
 * 🛠️ SEMSAI CUSTOM QUERY TEMPLATE
 * 
 * Use this file to write your own logic to query the database.
 * 
 * HOW TO RUN:
 * 1. Write your code inside the `run()` function.
 * 2. Open terminal.
 * 3. Run: node scripts/query_template.js
 */

import mongoose from 'mongoose';
import dotenv from 'dotenv';

// ✅ ALL MODELS IMPORTED
import Compound from '../models/Compound.js';
import Unit from '../models/Unit.js';
import Residential from '../models/Residential.js';
import Developer from '../models/Developer.js';
import User from '../models/User.js';
import Location from '../models/Location.js';
import Media from '../models/Media.js';
import Contact from '../models/Contact.js';
import Payment from '../models/Payment.js';
// Smart Scoring & Metrics
import CompoundScores from '../models/CompoundScores.js';
import MarketMetrics from '../models/MarketMetrics.js';
import PriceHistory from '../models/PriceHistory.js';

// Load variables from .env
dotenv.config();

const run = async () => {
    try {
        // 1. Connect to Database (Do not touch)
        await mongoose.connect(process.env.MONGO_URI);
        console.log('✅ Connected to MongoDB\n');

        // ==========================================
        // 👇 WRITE YOUR CODE BELOW THIS LINE 👇
        // ==========================================

        console.log("Hello! Writing my custom query...");

        // EXAMPLE 1: Find 3 Compounds
        // const comps = await Compound.find({}).limit(3);
        // console.log(comps);

        // EXAMPLE 2: Count Units with price > 10M
        // const expensiveCount = await Unit.countDocuments({ price: { $gt: 10000000 } });
        // console.log(`Super expensive units: ${expensiveCount}`);

        // ==========================================
        // 👆 WRITE YOUR CODE ABOVE THIS LINE 👆
        // ==========================================

    } catch (error) {
        console.error('❌ Error executing query:', error);
    } finally {
        // 3. Disconnect (Do not touch)
        await mongoose.connection.close();
        console.log('\n🔌 Disconnected');
    }
};

// Execute the function
run();
