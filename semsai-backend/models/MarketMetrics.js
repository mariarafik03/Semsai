import mongoose from 'mongoose';

const marketMetricsSchema = new mongoose.Schema({
    compound_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Compound', required: true },

    // Location Growth Indicators
    infrastructure_index: { type: Number, min: 0, max: 1 }, // Proximity to schools, hospitals, malls
    demand_growth: Number, // % increase in search/inquiry volume

    // Liquidity Metrics
    avg_resale_listings: Number, // Number of active resale listings
    rent_yield: Number, // Annual rent / purchase price
    location_access_score: { type: Number, min: 0, max: 1 }, // Proximity to highways, metro

    // Calculated Scores (Updated periodically)
    location_growth_score: Number,
    resale_liquidity_score: Number,
    rental_demand_score: Number,

    last_updated: { type: Date, default: Date.now }

}, { timestamps: true });

// Index for quick lookups
marketMetricsSchema.index({ compound_id: 1 });

const MarketMetrics = mongoose.model('MarketMetrics', marketMetricsSchema, 'market_metrics');

export default MarketMetrics;
