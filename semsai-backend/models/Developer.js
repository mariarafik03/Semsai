import mongoose from 'mongoose';

const developerSchema= new mongoose.Schema({
    dev_name: String,
    projects_completed: Number,
    total_projects: Number,
    specialization: String,
    rating:Number,
    dev_history: String,
}, {timestamps:true});

const Developer= mongoose.model('Developer',developerSchema, 'developers');

export default Developer;