import mongoose from 'mongoose';

const priceHistorySchema = new mongoose.Schema({
    compound_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Compound', required: true },
    year: { type: Number, required: true },
    month: { type: Number, min: 1, max: 12 },

    // Price metrics
    avg_sale_price: Number,
    avg_rent_price: Number,
    min_price: Number,
    max_price: Number,

    // Market activity
    transaction_volume: { type: Number, default: 0 },
    avg_days_on_market: Number,

    // Derived metrics
    price_change_rate: Number, // % change from previous period
    price_stability: Number, // Lower variance = higher stability (0-1)
    occupancy_rate: Number, // 0-1

}, { timestamps: true });

// Compound index for efficient queries
priceHistorySchema.index({ compound_id: 1, year: -1, month: -1 });

const PriceHistory = mongoose.model('PriceHistory', priceHistorySchema, 'price_history');

export default PriceHistory;
