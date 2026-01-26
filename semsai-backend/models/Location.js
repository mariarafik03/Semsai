import mongoose from 'mongoose';

const locationSchema = new mongoose.Schema({
    // Location can be specific to a unit or a compound
    compound_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Compound' },
    unit_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Unit' },
    
    city: String,
    district: String,
    neighborhood: String,
    lat: Number,
    long: Number
}, { timestamps: true });

const Location = mongoose.model('Location', locationSchema, 'location');

export default Location;
