import mongoose from 'mongoose';
import dotenv from 'dotenv';
import Compound from '../models/Compound.js';
import fetch from 'node-fetch';

dotenv.config();

const MONGO_URI = process.env.MONGO_URI || 'mongodb+srv://semsai_user:EA-xQASp73Y9_fF@cluster0.vdtyjnl.mongodb.net/semsai?retryWrites=true&w=majority&appName=Cluster0';

async function backfill() {
    console.log('Starting Backfill of Compound IDs using Locations API...');
    await mongoose.connect(MONGO_URI);
    
    // Find compounds without propertyfinder_id
    const compounds = await Compound.find({ 
        $or: [
            { propertyfinder_id: { $exists: false } },
            { propertyfinder_id: null }
        ]
    });
    console.log(`Found ${compounds.length} compounds needing ID backfill.`);

    for (const compound of compounds) {
        if (!compound.name || compound.name === 'Unknown Compound' || compound.name === 'Independent') continue;
        
        console.log(`Searching for ID for: ${compound.name}`);
        try {
            const url = `https://www.propertyfinder.eg/api/pwa/locations?locale=en&filters.name=${encodeURIComponent(compound.name)}&pagination.limit=5`;
            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'x-pf-source': 'pwa'
                }
            });

            if (!response.ok) {
                console.warn(`  - API error (${response.status}) for ${compound.name}`);
                continue;
            }

            const json = await response.json();
            const results = json.data?.attributes || [];
            
            // Look for a compound match
            const match = results.find(loc => 
                (loc.location_type === 'COMPOUND' || loc.location_type === 'TOWER') &&
                (loc.name.toLowerCase() === compound.name.toLowerCase() || 
                 compound.name.toLowerCase().includes(loc.name.toLowerCase()))
            ) || results[0]; // Fallback to first result if it seems related

            if (match && match.id) {
                compound.propertyfinder_id = String(match.id);
                // Also capture slug for future Community Insights scraping if needed
                if (match.slug) {
                    compound.set('propertyfinder_slug', match.slug);
                }
                await compound.save();
                console.log(`  - Found ID: ${match.id} (${match.name})`);
            } else {
                console.log(`  - No ID match found for ${compound.name}`);
            }
        } catch (err) {
            console.error(`  - Error searching for ${compound.name}:`, err.message);
        }
        
        await new Promise(r => setTimeout(r, 500)); // Be gentle
    }

    await mongoose.disconnect();
    console.log('Backfill Complete.');
}

backfill();
