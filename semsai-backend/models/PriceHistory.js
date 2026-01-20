import mongoose from 'mongoose';

const priceHistorySchema = new mongoose.Schema({
    unit_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Unit', required: true },
    old_price: Number,
    new_price: Number,
    date_changed: { type: Date, default: Date.now }
}, { timestamps: true });

const PriceHistory = mongoose.model('PriceHistory', priceHistorySchema, 'price_history');

export default PriceHistory;
