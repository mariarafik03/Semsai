import express from 'express';
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import cors from 'cors';
import User from './models/User.js';
import Developer from './models/Developer.js';
import Compound from './models/Compound.js';
import Unit from './models/Unit.js';
import axios from 'axios';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// Simple request logger
app.use((req, res, next) => {
  console.log(`${req.method} ${req.originalUrl}`);
  next();
});

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

// Forgot Password – check email exists, update password
app.post('/auth/forgot-password', async (req, res) => {
  const email = req.body.email?.toLowerCase();
  const newPass = req.body.newPass;
  if (!email || !newPass) {
    return res.status(400).json({ error: 'Email and new password are required' });
  }
  try {
    const user = await User.findOne({ email });
    if (!user) {
      return res.status(404).json({ error: 'No account found with this email' });
    }
    user.pass = newPass;
    await user.save();
    res.json({ message: 'Password updated successfully' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to reset password' });
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
    const pythonServiceUrl = process.env.AGENTS_URL || 'http://127.0.0.1:8000/agents/step';
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


// ─── Compounds (Explore Map) ───
// Returns all compounds that have lat/lng for map markers
app.get('/compounds/map', async (req, res) => {
  try {
    const compounds = await Compound.find(
      { lat: { $exists: true, $ne: null }, lng: { $exists: true, $ne: null } },
      {
        name: 1,
        lat: 1,
        lng: 1,
        location: 1,
        developer_name: 1,
        unit_count: 1,
        developer_start_price: 1,
        resale_start_price: 1,
        images_urls: { $slice: 1 },   // only first image for card thumbnail
      }
    ).lean();
    res.json(compounds);
  } catch (err) {
    console.error('Compounds map error:', err);
    res.status(500).json({ error: 'Failed to fetch compounds' });
  }
});

// Returns units belonging to a specific compound
app.get('/compounds/:id/units', async (req, res) => {
  try {
    const compoundId = req.params.id;
    let objectId;
    try {
      objectId = new mongoose.Types.ObjectId(compoundId);
    } catch {
      return res.status(400).json({ error: 'Invalid compound ID' });
    }

    // compound_id can be stored as ObjectId or string
    const units = await Unit.find(
      { $or: [{ compound_id: objectId }, { compound_id: compoundId }] },
      {
        name: 1,
        property_type: 1,
        unit_type: 1,
        price: 1,
        price_min: 1,
        price_max: 1,
        area: 1,
        area_min: 1,
        area_max: 1,
        bedrooms: 1,
        bathrooms: 1,
        finishing: 1,
        sale_type: 1,
        delivery_year: 1,
        images: 1,
        compound_name: 1,
        developer_name: 1,
        location: 1,
        description: 1,
        payment_plans: 1,
      }
    ).limit(50).lean();

    res.json(units);
  } catch (err) {
    console.error('Compound units error:', err);
    res.status(500).json({ error: 'Failed to fetch units' });
  }
});

// Returns a single compound with full details
app.get('/compounds/:id', async (req, res) => {
  try {
    const compoundId = req.params.id;
    let objectId;
    try {
      objectId = new mongoose.Types.ObjectId(compoundId);
    } catch {
      return res.status(400).json({ error: 'Invalid compound ID' });
    }

    const compound = await Compound.findById(objectId).lean();
    if (!compound) return res.status(404).json({ error: 'Compound not found' });

    // Also get the unit count from the units collection
    const unitCount = await Unit.countDocuments({ $or: [{ compound_id: objectId }, { compound_id: compoundId }] });
    compound.actual_unit_count = unitCount;

    res.json(compound);
  } catch (err) {
    console.error('Compound detail error:', err);
    res.status(500).json({ error: 'Failed to fetch compound' });
  }
});

// ─── Listings (all units with pagination + filters) ───
app.get('/units/listings', async (req, res) => {
  try {
    const page = Math.max(1, parseInt(req.query.page) || 1);
    const limit = Math.min(50, parseInt(req.query.limit) || 20);
    const skip = (page - 1) * limit;

    const filter = {};

    if (req.query.region) {
      filter.location = { $regex: req.query.region, $options: 'i' };
    }
    if (req.query.type) {
      filter.property_type = { $regex: `^${req.query.type}$`, $options: 'i' };
    }
    if (req.query.bedrooms) {
      const beds = parseInt(req.query.bedrooms);
      if (beds > 0) filter.bedrooms = beds;
    }
    if (req.query.minPrice || req.query.maxPrice) {
      filter.$or = [];
      const priceFilter = {};
      if (req.query.minPrice) priceFilter.$gte = parseFloat(req.query.minPrice);
      if (req.query.maxPrice) priceFilter.$lte = parseFloat(req.query.maxPrice);
      filter.$or.push({ price: priceFilter });
      filter.$or.push({ price_min: priceFilter });
    }
    if (req.query.search) {
      const searchRegex = { $regex: req.query.search, $options: 'i' };
      const searchOr = [
        { compound_name: searchRegex },
        { developer_name: searchRegex },
        { name: searchRegex },
        { location: searchRegex },
      ];
      if (filter.$or) {
        filter.$and = [{ $or: filter.$or }, { $or: searchOr }];
        delete filter.$or;
      } else {
        filter.$or = searchOr;
      }
    }

    let sort = { scraped_at: -1 };
    switch (req.query.sort) {
      case 'price_asc': sort = { price: 1 }; break;
      case 'price_desc': sort = { price: -1 }; break;
      case 'area_asc': sort = { area: 1 }; break;
      case 'area_desc': sort = { area: -1 }; break;
      case 'newest': default: sort = { scraped_at: -1 }; break;
    }

    const [units, total] = await Promise.all([
      Unit.find(filter, {
        name: 1, property_type: 1, price: 1, price_min: 1, price_max: 1,
        area: 1, area_min: 1, area_max: 1, bedrooms: 1, bathrooms: 1,
        finishing: 1, sale_type: 1, delivery_year: 1, images: { $slice: 1 },
        compound_name: 1, developer_name: 1, location: 1, description: 1,
        payment_plans: 1,
      }).sort(sort).skip(skip).limit(limit).lean(),
      Unit.countDocuments(filter),
    ]);

    res.json({ units, total, page, totalPages: Math.ceil(total / limit) });
  } catch (err) {
    console.error('Listings error:', err);
    res.status(500).json({ error: 'Failed to fetch listings' });
  }
});

// ─── Listings filter options (distinct regions + types) ───
app.get('/units/filters', async (req, res) => {
  try {
    const [regions, types] = await Promise.all([
      Unit.distinct('location'),
      Unit.distinct('property_type'),
    ]);

    const cleanRegions = regions
      .filter(r => r && r.trim())
      .map(r => {
        const parts = r.split(',').map(p => p.trim());
        return parts.length >= 2 ? parts[parts.length - 2] : parts[0];
      })
      .filter(Boolean);

    const regionCounts = {};
    cleanRegions.forEach(r => { regionCounts[r] = (regionCounts[r] || 0) + 1; });
    const sortedRegions = Object.entries(regionCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 25)
      .map(([name, count]) => ({ name, count }));

    const cleanTypes = types.filter(t => t && t.trim()).sort();

    res.json({ regions: sortedRegions, types: cleanTypes });
  } catch (err) {
    console.error('Filters error:', err);
    res.status(500).json({ error: 'Failed to fetch filters' });
  }
});

// Returns a single unit with full details
app.get('/units/:id', async (req, res) => {
  try {
    let objectId;
    try {
      objectId = new mongoose.Types.ObjectId(req.params.id);
    } catch {
      return res.status(400).json({ error: 'Invalid unit ID' });
    }
    const unit = await Unit.findById(objectId).lean();
    if (!unit) return res.status(404).json({ error: 'Unit not found' });

    if (unit.compound_id) {
      const compound = await Compound.findById(unit.compound_id, {
        name: 1, location: 1, developer_name: 1, images_urls: { $slice: 3 },
        amenities: 1, description: 1,
      }).lean();
      if (compound) unit.compound_info = compound;
    }
    res.json(unit);
  } catch (err) {
    console.error('Unit detail error:', err);
    res.status(500).json({ error: 'Failed to fetch unit' });
  }
});

// ─── Explore Areas ───
app.get('/explore/areas', async (req, res) => {
  try {
    const areas = await Compound.aggregate([
      { $match: { location: { $exists: true, $ne: null, $ne: '' } } },
      { $group: { _id: '$location', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 15 },
    ]);
    const totalCompounds = await Compound.countDocuments();
    const totalUnits = await Unit.countDocuments();
    res.json({
      areas: areas.map(a => ({ name: a._id, count: a.count })),
      totalCompounds,
      totalUnits,
    });
  } catch (err) {
    console.error('Areas error:', err);
    res.status(500).json({ error: 'Failed to fetch areas' });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
