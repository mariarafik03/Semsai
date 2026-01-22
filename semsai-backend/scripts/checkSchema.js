
import mongoose from 'mongoose';

const MONGO_URI = 'mongodb+srv://semsai_user:EA-xQASp73Y9_fF@cluster0.vdtyjnl.mongodb.net/semsai?retryWrites=true&w=majority&appName=Cluster0';

async function checkSchema() {
    try {
        await mongoose.connect(MONGO_URI);
        console.log('Connected to MongoDB');

        const collections = await mongoose.connection.db.listCollections().toArray();
        console.log('Collections:', collections.map(c => c.name));

        // Sample a few collections to see schema
        for (const col of collections) {
            if (['compounds', 'units', 'properties', 'listings'].includes(col.name)) {
                const sample = await mongoose.connection.db.collection(col.name).findOne({});
                console.log(`\nSample from ${col.name}:`, JSON.stringify(sample, null, 2));
            }
        }

    } catch (err) {
        console.error('Error:', err);
    } finally {
        await mongoose.disconnect();
    }
}

checkSchema();
