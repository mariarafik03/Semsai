import mongoose from 'mongoose';

const compoundSchema = new mongoose.Schema({
    name: { type: String, required: true },
    propertyfinder_id: { type: String, index: true }, // ID for Price Trends API
    propertyfinder_slug: String, // Slug for Area Insights pages
    description: String,
    location: String, // General location name like "New Cairo"
    area: Number, // Total area in sqm
    phases: Number,
    completed_phases: Number,

    lat: Number,
    lng: Number,

    // Developer Relationship
    developer_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Developer' },

    // New Fields for Enhanced Schema
    gated: Boolean,
    security_level: { type: Number, min: 1, max: 5 },
    delivery_year: Number,
    layout_style: { type: String, enum: ['modern', 'luxury', 'mixed'] },

    // Market History (Aggregated Stats)
    market_history: [{
        year: Number,
        avg_sale_price: Number,
        avg_rent_price: Number,
        occupancy_rate: Number
    }],

    amenities: [String], // Changed to array of strings for flexibility
    // amenities: { ... } // (Old object schema removed for flexibility)

    // Captured Payment Info (Summary)
    payment_plans_summary: String,
    is_gated: { type: Boolean, default: true },
    unit_count: Number,

    // Financial Calculation Assumptions (Defaults per compound)
    financial_profile: {
        vacancy_rate: { type: Number, default: 5 }, // Percentage (0-100)
        property_tax_rate: { type: Number, default: 1.5 }, // Percentage of unit price
        insurance_cost: { type: Number, default: 2000 }, // Fixed annual cost
        maintenance_cost: { type: Number, default: 5000 }, // Fixed annual cost
        management_fee_rate: { type: Number, default: 10 }, // Percentage of gross rent
        utilities_cost: { type: Number, default: 0 } // Fixed annual cost (if landlord pays)
    }
}, { timestamps: true });

// Speed up the explore map query that filters by lat/lng existence
compoundSchema.index({ lat: 1, lng: 1 });

const Compound = mongoose.model('Compound', compoundSchema, 'compounds');

export default Compound;
