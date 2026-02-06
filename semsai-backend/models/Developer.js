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
    developer_score: Number // Calculated score
}, { timestamps: true });

const Developer = mongoose.model('Developer', developerSchema, 'developers');

export default Developer;