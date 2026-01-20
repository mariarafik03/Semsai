import mongoose from 'mongoose';

const residentialSchema = new mongoose.Schema({
    unit_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Unit', required: true },
    bedrooms: Number,
    bathrooms: Number,
    finishing: String,
    floor_num: Number
}, { timestamps: true });

const Residential = mongoose.model('Residential', residentialSchema, 'residential');

export default Residential;
