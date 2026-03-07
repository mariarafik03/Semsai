import mongoose from 'mongoose';

const developerSchema = new mongoose.Schema({
    dev_name: String,
    projects_completed: Number,
    total_projects: Number,
    specialization: String,
    rating: Number,
    dev_history: String,

    years_active: Number,
    google_reviews_score: { type: Number, default: 0 },
    facebook_reviews_score: { type: Number, default: 0 },
    delivery_delays: { type: String, enum: ['None', 'Low', 'High'], default: 'None' },
    developer_score: Number,

    // Extended fields from scraping
    areas: [String],
    compound_ids: [{ type: mongoose.Schema.Types.ObjectId }],
    compound_names: [String],
    compounds_count: Number,
    description: String,
    logo_url: String,
    phone: String,
    website: String,
    price_min: Number,
    price_max: Number,
    Developer_Class: String,
    nawy_url: String,
}, { timestamps: true, strict: false });

const Developer = mongoose.model('Developer', developerSchema, 'developers');

export default Developer;