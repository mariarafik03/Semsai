import mongoose from 'mongoose';

const userSchema = new mongoose.Schema({
  name: { type: String, required: true },
  pass: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  profession: { type: String },
  occupation: { type: String },
  dev_preference: [{ type: String }],
  amenities: [{ type: String }],
  savedLocations: [{
    name: { type: String, required: true },
    lat: { type: Number, required: true },
    lng: { type: Number, required: true },
    address: { type: String }
  }]
}, { timestamps: true });

const User = mongoose.model('User', userSchema, 'users');

export default User;
