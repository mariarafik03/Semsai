
/**
 * 🛠️ SEMSAI CUSTOM QUERY TEMPLATE
 */

import mongoose from 'mongoose';
import dotenv from 'dotenv';
import Compound from '../models/Compound.js';
import Unit from '../models/Unit.js';

dotenv.config();

const run = async () => {
    try {
        await mongoose.connect(process.env.MONGO_URI);
        console.log('✅ Connected to MongoDB\n');

        // ==========================================
        // 🔍 FIND UNITS BY ID: 697155d794190b07bca8ac60
        // ==========================================
        const targetId = '697155d794190b07bca8ac60';
        console.log(`Searching for units with Compound ID: ${targetId}...\n`);

        const units = await Unit.find({ compound_id: targetId });

        console.log(`\n📦 Found ${units.length} units:\n`);

        if (units.length > 0) {
            units.forEach((unit, i) => {
                console.log(`#${i + 1} Type: ${unit.type}`);
                console.log(`    Price: ${unit.price ? unit.price.toLocaleString() + ' EGP' : 'N/A'}`);
                console.log(`    URL: ${unit.url || 'N/A'}`);
                console.log('----------------');
            });
        }

    } catch (error) {
        console.error('❌ Error executing query:', error);
    } finally {
        await mongoose.connection.close();
        console.log('\n🔌 Disconnected');
    }
};

run();
