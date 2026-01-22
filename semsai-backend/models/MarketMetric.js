
import mongoose from 'mongoose';

const marketMetricSchema = new mongoose.Schema({
    compound_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Compound', required: true },
    type: { type: String, enum: ['Apartment', 'Villa'], required: true },
    transaction_type: { type: String, enum: ['Buy', 'Rent'], required: true },
    period: { type: String, enum: ['1Y', '2Y', '5Y'], default: '1Y' },
    history: [{
        date: Date,
        avg_price: Number,
        community_avg_price: Number
    }],
    last_updated: { type: Date, default: Date.now }
}, { timestamps: true, strict: false });

const MarketMetric = mongoose.model('MarketMetric', marketMetricSchema, 'market_metrics');

export default MarketMetric;
