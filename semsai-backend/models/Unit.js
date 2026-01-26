import mongoose from 'mongoose';

const unitSchema = new mongoose.Schema({
    compound_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Compound', required: true },
    type: { type: String, required: true }, // e.g., "apartment", "villa"
    area: Number, // Size in sqm
    price: Number, // Current price
    url: { type: String, unique: true, sparse: true }, // Store scraped URL to prevent duplicates

    delivery_year: Number,
    delivery_date: Date, // Kept for backward compatibility or full timestamps
    finishing: String, // e.g., "fully_finished", "core_shell"
    view: String, // e.g., "garden", "street"
    status: { type: String, default: 'Available' },

    // Geographic Coordinates
    lat: Number,
    lng: Number,

    // Unit specific amenities (if any)
    amenities: [String]
}, { timestamps: true });

const Unit = mongoose.model('Unit', unitSchema, 'units');

export default Unit;
