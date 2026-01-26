import express from 'express';
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import cors from 'cors';
import User from './models/User.js';
import Developer from './models/Developer.js';
import axios from 'axios';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// connect to Atlas
mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log('MongoDB connected'))
  .catch((err) => console.error('Mongo error', err));

// Route
app.get('/', (req, res) => {
  res.json({ message: 'SemsAi API running' });
});

// User
app.post('/users', async (req, res) => {
  try {
     const user = await User.create(req.body);
    res.status(201).json(user);
  } catch (err) {
    console.error(err);
    res.status(400).json({ error: 'Cannot create user' });
  }
});

app.get('/users', async (req, res) => {
  const users = await User.find();
  res.json(users);
});

// User Locations
app.post('/users/locations', async (req, res) => {
  const { email, location } = req.body;
  try {
    const user = await User.findOne({ email });
    if (!user) return res.status(404).json({ error: 'User not found' });
    
    user.savedLocations.push(location);
    await user.save();
    res.status(201).json(user.savedLocations);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to save location' });
  }
});

app.get('/users/locations', async (req, res) => {
  const { email } = req.query;
  try {
    const user = await User.findOne({ email });
    if (!user) return res.status(404).json({ error: 'User not found' });
    res.json(user.savedLocations);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to fetch locations' });
  }
});

app.delete('/users/locations/:id', async (req, res) => {
  const { email } = req.body;
  const locationId = req.params.id;

  try {
      const user = await User.findOne({ email });
      if (!user) return res.status(404).json({ error: 'User not found' });

      user.savedLocations.pull({ _id: locationId });
      await user.save();
      
      res.status(200).json(user.savedLocations);
  } catch (err) {
      console.error(err);
      res.status(500).json({ error: 'Failed to delete location' });
  }
});

// Auth
app.post('/auth/register',async (req,res) => {
try {
    const body = { ...req.body, email: req.body.email.toLowerCase() };
    const user = await User.create(body);
    res.status(201).json(user);
  }

  catch (err) {
      console.error(err);
      if (err.code === 11000) {
        return res.status(409).json({ error: 'Email already exists' });
      }
      res.status(400).json({ error: 'Cannot register user' });
    }
});


app.post('/auth/login', async (req, res) => {
  const email=req.body.email.toLowerCase();
  const pass=req.body.pass;
  try {
    const user = await User.findOne({ email, pass });
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    res.json(user);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Login error' });
  }
});

// Developers
app.get('/developers', async (req, res) => {
  const devs = await Developer.find();
  res.json(devs);
});

// Conversation Step (Proxy to Python)

app.post('/conversation/step', async (req, res) => {
  try {
    const pythonServiceUrl = 'http://127.0.0.1:8000/agents/step';
    const response = await axios.post(pythonServiceUrl, req.body);
    res.json(response.data);
  } catch (err) {
    console.error('Python service error:', err.message);
    res.status(500).json({ error: 'Failed to communicate with agents service' });
  }
});

// Recommendations
app.post('/recommendations', async (req, res) => {
  try {
    const { state } = req.body;
    if (!state) return res.status(400).json({ error: 'State is required' });

    const unitsCollection = mongoose.connection.collection('units');
    
    // Build Match Stage for Payments
    let paymentMatch = {};
    if (state.payment_type && state.payment_type.toLowerCase() === 'cash') {
        paymentMatch['payment.cash'] = true;
        if (state.budget) {
            paymentMatch['payment.down_payment'] = { $lte: parseInt(state.budget) };
        }
    } else if (state.payment_type && state.payment_type.toLowerCase() === 'installments') {
        paymentMatch['payment.cash'] = false; // or query based on existence
        if (state.Downpayment) {
            paymentMatch['payment.down_payment'] = { $lte: parseInt(state.Downpayment) };
        }
        if (state.monthlyinstall) {
            paymentMatch['payment.monthly_installment'] = { $lte: parseInt(state.monthlyinstall) };
        }
    }

    // Location Match (after lookup)
    let locationMatch = {};
    if (state.location) {
        locationMatch['compound.location'] = { $regex: state.location, $options: 'i' };
    }

    const pipeline = [
        // 1. Join Payments
        {
            $lookup: {
                from: 'payments',
                localField: '_id',
                foreignField: 'unit_id',
                as: 'payment'
            }
        },
        { $unwind: '$payment' },
        
        // 2. Filter Payments
        { $match: paymentMatch },

        // 3. Join Compounds
        {
            $lookup: {
                from: 'compounds',
                localField: 'compound_id',
                foreignField: '_id',
                as: 'compound'
            }
        },
        { $unwind: '$compound' },

        // 4. Filter Location
        { $match: locationMatch },

        // 5. Join Developers
        {
            $lookup: {
                from: 'developers',
                localField: 'dev_id',
                foreignField: '_id',
                as: 'developer'
            }
        },
        { $unwind: '$developer' },

        { $limit: 10 }
    ];

    const results = await unitsCollection.aggregate(pipeline).toArray();
    
    // Transform shape if needed (user asked for {unit, compound, developer})
    const formatted = results.map(item => ({
        unit: {
            _id: item._id,
            type: item.type,
            area: item.area,
            price: item.payment.down_payment, // approx
             // destructure other unit fields excluding joined ones if they merged?
             // MongoDB aggregation merges fields? No, lookup 'as' puts them in subfields.
             // But the root object 'item' contains unit fields + 'payment', 'compound', 'developer'.
            ...item
        },
        compound: item.compound,
        developer: item.developer,
        payment: item.payment
    }));

    // Cleanup duplicate refs in formatted if needed, but above is okay-ish.
    // Better to explicitly separate:
    const cleanResults = results.map(item => {
        const { compound, developer, payment, ...unitFields } = item;
        return {
            unit: unitFields,
            compound,
            developer,
            payment
        };
    });

    res.json(cleanResults);

  } catch (err) {
    console.error('Recommendations error:', err);
    res.status(500).json({ error: 'Failed to fetch recommendations' });
  }
});


const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
