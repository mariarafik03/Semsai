import mongoose from 'mongoose';

const contactSchema = new mongoose.Schema({
    method: String, // e.g., "phone", "email", "whatsapp"
    name: String, // Contact person name
    value: String, // The number or email
    compound_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Compound' }
}, { timestamps: true });

const Contact = mongoose.model('Contact', contactSchema, 'contact');

export default Contact;
