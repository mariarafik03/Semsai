import mongoose from 'mongoose';

const mediaSchema = new mongoose.Schema({
    compound_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Compound' },
    unit_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Unit' },
    
    url: { type: String, required: true },
    type: String // e.g., "image", "video", "floor_plan"
}, { timestamps: true });

const Media = mongoose.model('Media', mediaSchema, 'media');

export default Media;
