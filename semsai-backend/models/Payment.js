import mongoose from 'mongoose';

const paymentSchema = new mongoose.Schema({
    unit_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Unit' },
    compound_id: { type: mongoose.Schema.Types.ObjectId, ref: 'Compound' }, // If a payment plan is generic for the compound
    
    down_payment: Number,
    monthly_installment: Number,
    duration: Number, // In months
    cash: Boolean, // If it's a cash price
    
    // Additional CSV fields if any
    plan_name: String
}, { timestamps: true });

const Payment = mongoose.model('Payment', paymentSchema, 'payments');

export default Payment;
