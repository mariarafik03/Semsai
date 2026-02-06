import mongoose from 'mongoose';
import dotenv from 'dotenv';
import Compound from '../models/Compound.js';
import CompoundScores from '../models/CompoundScores.js';
import MarketMetrics from '../models/MarketMetrics.js';
import Developer from '../models/Developer.js';

dotenv.config();

const calculateScores = async () => {
    await mongoose.connect(process.env.MONGO_URI);
    console.log('MongoDB Connected');

    const compounds = await Compound.find();
    console.log(`Processing ${compounds.length} compounds...`);

    for (const compound of compounds) {
        try {
            // 1. Calculate Privacy Score
            const gatedScore = compound.is_gated ? 0.4 : 0;
            const securityScore = compound.security_level ? (compound.security_level / 5) * 0.3 : 0;
            const densityScore = compound.unit_count && compound.total_area
                ? Math.max(0, 0.3 * (1 - (compound.unit_count / compound.total_area) / 0.01))
                : 0;
            const privacy_score = gatedScore + securityScore + densityScore;

            // 2. Calculate Layout Match Score (Modernity)
            const currentYear = new Date().getFullYear();
            const deliveryScore = compound.delivery_year
                ? Math.min(1, 0.7 * (compound.delivery_year > 2018 ? 1 : 0))
                : 0;
            const styleScore = compound.layout_style === 'modern' ? 0.3 : 0;
            const layout_match_score = deliveryScore + styleScore;

            // 3. Calculate Landscape Score
            const landscape_score = compound.green_area && compound.total_area
                ? compound.green_area / compound.total_area
                : 0;

            // 4. Calculate Nightlife Score
            const amenities = compound.amenities || {};
            const nightlife_score = (
                (amenities.cafes ? 0.33 : 0) +
                (amenities.restaurants ? 0.33 : 0) +
                (amenities.nightlife_nearby ? 0.34 : 0)
            );

            // 5. Calculate Unit Density
            const unit_density = compound.unit_count && compound.total_area
                ? compound.unit_count / compound.total_area
                : 0;

            // Save CompoundScores
            await CompoundScores.findOneAndUpdate(
                { compound_id: compound._id },
                {
                    privacy_score,
                    layout_match_score,
                    landscape_score,
                    nightlife_score,
                    unit_density,
                    modernity_score: layout_match_score,
                    last_calculated: new Date()
                },
                { upsert: true }
            );

            // Initialize MarketMetrics with placeholder values
            await MarketMetrics.findOneAndUpdate(
                { compound_id: compound._id },
                {
                    infrastructure_index: 0.5, // Placeholder
                    demand_growth: 0,
                    avg_resale_listings: 0,
                    rent_yield: 0,
                    location_access_score: 0.5, // Placeholder
                    location_growth_score: 0,
                    resale_liquidity_score: 0,
                    rental_demand_score: 0,
                    last_updated: new Date()
                },
                { upsert: true }
            );

            console.log(`✓ Processed: ${compound.name}`);

        } catch (err) {
            console.error(`Error processing ${compound.name}:`, err.message);
        }
    }

    // ==========================================
    // 6. Calculate Developer Scores
    // ==========================================
    const developers = await Developer.find();
    console.log(`Processing ${developers.length} developers...`);

    const calculateDeveloperScore = (rating, totalProjects) => {
        if (rating == null || totalProjects == null) return null;

        const projectScore = Math.log(totalProjects + 1);

        const score =
            (rating * 0.7) +
            (projectScore * 0.3);

        return Number(score.toFixed(3));
    };

    for (const dev of developers) {
        try {
            const score = calculateDeveloperScore(dev.rating, dev.total_projects);

            if (score !== null) {
                await Developer.findByIdAndUpdate(dev._id, { developer_score: score });
                console.log(`✓ Developer: ${dev.dev_name} -> Score: ${score}`);
            } else {
                console.log(`⚠️ Developer: ${dev.dev_name} -> Skipped (Missing Data)`);
            }
        } catch (err) {
            console.error(`Error processing developer ${dev.dev_name}:`, err.message);
        }
    }

    console.log('Score calculation complete!');
    process.exit(0);
};

calculateScores().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
});
