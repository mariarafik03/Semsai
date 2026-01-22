import mongoose from 'mongoose';

const compoundSchema = new mongoose.Schema({
    name: { type: String, required: true },
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
    
    amenities: {
        clubhouse: Boolean,
        gym: Boolean,
        cafes: Boolean,
        restaurants: Boolean,
        parks: Boolean,
        nightlife_nearby: Boolean,
        commercial_strip: Boolean,
        food_court: Boolean,
        outdoor_pools: Boolean,
        children_play_area: Boolean,
        barbecue_area: Boolean,
        bicycle_lanes: Boolean,
        jogging_trail: Boolean
    },
    is_gated: { type: Boolean, default: true },
    unit_count: Number
}, { timestamps: true });

const Compound = mongoose.model('Compound', compoundSchema, 'compounds');

export default Compound;
