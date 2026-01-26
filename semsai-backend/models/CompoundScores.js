import mongoose from 'mongoose';

const compoundScoresSchema = new mongoose.Schema({
    compound_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Compound', required: true, unique: true },

    // Calculated Scores (0-1 scale)
    privacy_score: Number,
    layout_match_score: Number,
    landscape_score: Number, // Nature/green areas
    nightlife_score: Number,

    // Derived fields for calculations
    unit_density: Number, // units per sqm
    modernity_score: Number, // Based on delivery_year and layout_style

    last_calculated: { type: Date, default: Date.now }

}, { timestamps: true });

// Index for quick lookups
compoundScoresSchema.index({ compound_id: 1 });

const CompoundScores = mongoose.model('CompoundScores', compoundScoresSchema, 'compound_scores');

export default CompoundScores;
