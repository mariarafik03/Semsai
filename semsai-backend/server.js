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

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function toNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizePortfolioInput(body = {}) {
  const units = Array.isArray(body.units) ? body.units : [];
  return {
    netMonthlyIncome: toNumber(body.netMonthlyIncome),
    incomeType: (body.incomeType || 'salary').toString().toLowerCase(),
    monthlyFixedExpenses: toNumber(body.monthlyFixedExpenses),
    availableCash: toNumber(body.availableCash),
    creditAccess: Boolean(body.creditAccess),
    riskProfile: (body.riskProfile || 'moderate').toString().toLowerCase(),
    maxInstallmentRatio: toNumber(body.maxInstallmentRatio, 0.4),
    units: units.map((unit) => ({
      monthlyInstallment: toNumber(unit?.monthlyInstallment),
      remainingBalance: toNumber(unit?.remainingBalance),
      marketValue: toNumber(unit?.marketValue),
    })),
  };
}

function validatePortfolioInput(input) {
  if (input.netMonthlyIncome <= 0) return 'netMonthlyIncome must be greater than 0';
  if (input.monthlyFixedExpenses < 0) return 'monthlyFixedExpenses cannot be negative';
  if (input.availableCash < 0) return 'availableCash cannot be negative';
  if (input.maxInstallmentRatio <= 0 || input.maxInstallmentRatio > 1) {
    return 'maxInstallmentRatio must be between 0 and 1';
  }
  if (!['salary', 'freelance'].includes(input.incomeType)) {
    return "incomeType must be 'salary' or 'freelance'";
  }
  if (!['conservative', 'moderate', 'aggressive'].includes(input.riskProfile)) {
    return "riskProfile must be 'conservative', 'moderate', or 'aggressive'";
  }

  for (const unit of input.units) {
    if (unit.monthlyInstallment < 0 || unit.remainingBalance < 0 || unit.marketValue < 0) {
      return 'Unit values cannot be negative';
    }
  }

  return null;
}

function calculatePortfolio(input) {
  const totalInstallments = input.units.reduce(
    (sum, unit) => sum + unit.monthlyInstallment,
    0
  );
  const totalRemainingBalance = input.units.reduce(
    (sum, unit) => sum + unit.remainingBalance,
    0
  );
  const totalMarketValue = input.units.reduce((sum, unit) => sum + unit.marketValue, 0);

  const freeCashflow =
    input.netMonthlyIncome - input.monthlyFixedExpenses - totalInstallments;
  const dti = totalInstallments / input.netMonthlyIncome;
  const monthlyBurn = input.monthlyFixedExpenses + totalInstallments;
  const runwayMonths = monthlyBurn > 0 ? input.availableCash / monthlyBurn : 0;
  const riskBuffer = input.maxInstallmentRatio - dti;

  const cashflowScore = clamp(
    (freeCashflow / (input.netMonthlyIncome * 0.4)) * 100,
    0,
    100
  );

  let riskScore = clamp(
    (riskBuffer / input.maxInstallmentRatio) * 100,
    0,
    100
  );
  if (input.incomeType === 'freelance') {
    riskScore -= 15;
  }
  riskScore = clamp(riskScore, 0, 100);

  const liquidityScore = clamp((runwayMonths / 6) * 100, 0, 100);

  let flexibilityScore = 50;
  flexibilityScore += Math.min(input.units.length * 10, 30);
  if (input.creditAccess) flexibilityScore += 25;
  flexibilityScore = clamp(flexibilityScore, 0, 100);

  const finalScore = clamp(
    cashflowScore * 0.3 +
      riskScore * 0.3 +
      liquidityScore * 0.2 +
      flexibilityScore * 0.2,
    0,
    100
  );

  let healthBand = 'risky';
  if (finalScore >= 75) healthBand = 'healthy';
  else if (finalScore >= 50) healthBand = 'watch';

  return {
    inputSnapshot: input,
    metrics: {
      totalInstallments,
      totalRemainingBalance,
      totalMarketValue,
      freeCashflow,
      dti,
      runwayMonths,
      riskBuffer,
    },
    scores: {
      cashflowScore,
      riskScore,
      liquidityScore,
      flexibilityScore,
    },
    finalScore,
    healthBand,
  };
}

// ─── Validate required env vars ───
if (!process.env.MONGO_URI) {
  console.error('FATAL: MONGO_URI environment variable is not set!');
  console.error('Please add MONGO_URI as a Secret in HF Space Settings.');
  process.exit(1);
}

const app = express();

// Enhanced CORS configuration for HuggingFace Spaces
app.use(cors({
  origin: '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  expose_headers: ['Content-Type'],
  credentials: false,
  optionsSuccessStatus: 200
}));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));


app.use((req, res, next) => {
  console.log(`${req.method} ${req.originalUrl}`);
  next();
});

// connect to Atlas
mongoose.connect(process.env.MONGO_URI)
  .then(() => console.log('MongoDB connected'))
  .catch((err) => {
    console.error('Mongo connection error:', err.message);
    process.exit(1);
  });

// Root health check (supports GET + HEAD for UptimeRobot)
app.get('/', (req, res) => {
  res.json({ status: 'ok', message: 'SemsAi API running' });
});

app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    message: 'SemsAi Backend API running',
    timestamp: new Date().toISOString(),
    agents_url: process.env.AGENTS_URL || 'https://youssif12-semsai-agents.hf.space'
  });
});

app.head('/', (req, res) => {
  res.sendStatus(200);
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

// Forgot Password check email exists, update password
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

// Developer by name (case-insensitive search)
app.get('/developers/search', async (req, res) => {
  try {
    const { name } = req.query;
    if (!name) return res.status(400).json({ error: 'name query parameter required' });

    const dev = await Developer.findOne({
      dev_name: { $regex: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`, 'i') }
    }).lean();

    if (!dev) return res.status(404).json({ error: 'Developer not found' });
    res.json(dev);
  } catch (err) {
    console.error('Developer search error:', err.message);
    res.status(500).json({ error: 'Failed to fetch developer' });
  }
});

// Conversation Step (Proxy to Python Agents API on HuggingFace)
app.post('/conversation/step', async (req, res) => {
  try {
    // IMPORTANT: Use HuggingFace Spaces URL or environment variable
    const pythonServiceUrl = process.env.AGENTS_URL || 'https://youssif12-semsai-agents.hf.space/agents/step';
    console.log(`Proxying to agents service: ${pythonServiceUrl}`);
    
    const response = await axios.post(pythonServiceUrl, req.body, {
      timeout: 30000, // 30 second timeout
      headers: {
        'Content-Type': 'application/json'
      }
    });
    res.json(response.data);
  } catch (err) {
    console.error('Python service error:', err.message);
    console.error('Full error:', err);
    res.status(500).json({ 
      error: 'Failed to communicate with agents service',
      details: err.message,
      url: process.env.AGENTS_URL || 'https://youssif12-semsai-agents.hf.space/agents/step'
    });
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
      filter['property_type.name'] = { $regex: `^${req.query.type}$`, $options: 'i' };
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
      case 'price_asc': 
        sort = { price: 1 }; 
        filter.price = { $gt: 0 }; 
        break;
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
    // property_type is now an object {name: 'Apartment'}, so get distinct name
    const [regions, typesRaw, typeNames] = await Promise.all([
      Unit.distinct('location'),
      Unit.distinct('property_type'),
      Unit.distinct('property_type.name'),
    ]);

    const cleanRegions = regions
      .filter(r => r && typeof r === 'string' && r.trim())
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

    // Merge string types and object.name types
    const allTypes = new Set([
      ...typesRaw.filter(t => typeof t === 'string' && t.trim()).map(t => t.trim()),
      ...typeNames.filter(t => t && typeof t === 'string' && t.trim()),
    ]);
    const cleanTypes = [...allTypes].sort();

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

// Portfolio analysis (Phase 1 deterministic engine)
app.post('/portfolio/analyze', async (req, res) => {
  try {
    const input = normalizePortfolioInput(req.body);
    const validationError = validatePortfolioInput(input);

    if (validationError) {
      return res.status(400).json({ error: validationError });
    }

    const result = calculatePortfolio(input);
    return res.json(result);
  } catch (err) {
    console.error('Portfolio analyze error:', err);
    return res.status(500).json({ error: 'Failed to analyze portfolio' });
  }
});
// ─── Portfolio: Matching Units ───
app.post('/portfolio/matching-units', async (req, res) => {
  try {
    const { availableCash, freeCashflow, riskProfile, location, propertyType } = req.body;

    const maxBudget = toNumber(availableCash, 0);
    const maxInstallment = toNumber(freeCashflow, 0) * 0.6; // max 60% of free cashflow

    if (maxBudget <= 0 && maxInstallment <= 0) {
      return res.json({ units: [], message: 'Insufficient budget for new investments' });
    }

    // Build query
    const query = {};

    // Type filter
    if (propertyType) {
      const typeLower = propertyType.toLowerCase();
      query['$or'] = [
        { type: { $regex: new RegExp(`^${typeLower}$`, 'i') } },
        { property_type: { $regex: new RegExp(`^${typeLower}$`, 'i') } },
        { 'property_type.name': { $regex: new RegExp(`^${typeLower}$`, 'i') } },
      ];
    }

    // Location filter
    if (location) {
      query.location = { $regex: new RegExp(location, 'i') };
    }

    // Price filter: units affordable with available cash
    if (maxBudget > 0) {
      query['$and'] = query['$and'] || [];
      query['$and'].push({
        $or: [
          { price: { $lte: maxBudget, $gt: 0 } },
          { price_min: { $lte: maxBudget, $gt: 0 } },
        ]
      });
    }

    const units = await Unit.find(query)
      .sort({ price: 1 })
      .limit(20)
      .lean();

    // Return full documents so the client can render full detail screens
    const cleaned = units.map(u => {
      // Convert ObjectId to string
      u._id = u._id.toString();
      return u;
    });

    return res.json({ units: cleaned, count: cleaned.length });
  } catch (err) {
    console.error('Matching units error:', err);
    return res.status(500).json({ error: 'Failed to fetch matching units' });
  }
});

// ── Market Analytics API ─────────────────────────────────
// Area price comparison + Developer ranking using existing data.
// No historical data needed — uses current units collection.
app.get('/api/market-analytics', async (req, res) => {
  try {
    const db = mongoose.connection.db;

    // ── 1) Area Price Comparison ──
    // Aggregate avg price/sqm per location from units + compounds
    const areaPipeline = [
      {
        $lookup: {
          from: 'compounds',
          localField: 'compound_id',
          foreignField: '_id',
          as: 'compound',
        },
      },
      { $unwind: { path: '$compound', preserveNullAndEmptyArrays: false } },
      { $match: { price: { $gt: 0 }, area: { $gt: 0 } } },
      {
        $addFields: {
          price_per_sqm: { $divide: ['$price', '$area'] },
          location: '$compound.location',
        },
      },
      {
        $group: {
          _id: '$location',
          avg_price_per_sqm: { $avg: '$price_per_sqm' },
          min_price_per_sqm: { $min: '$price_per_sqm' },
          max_price_per_sqm: { $max: '$price_per_sqm' },
          avg_price: { $avg: '$price' },
          unit_count: { $sum: 1 },
          compound_names: { $addToSet: '$compound.name' },
        },
      },
      { $match: { _id: { $ne: null } } },
      { $sort: { avg_price_per_sqm: -1 } },
    ];

    const areaStats = await db.collection('units').aggregate(areaPipeline).toArray();

    const areas = areaStats.map((a) => ({
      location: a._id,
      avg_price_per_sqm: Math.round(a.avg_price_per_sqm),
      min_price_per_sqm: Math.round(a.min_price_per_sqm),
      max_price_per_sqm: Math.round(a.max_price_per_sqm),
      avg_price: Math.round(a.avg_price),
      unit_count: a.unit_count,
      compound_count: a.compound_names ? a.compound_names.length : 0,
    }));

    // ── 2) Developer Price Ranking ──
    const devPipeline = [
      {
        $lookup: {
          from: 'compounds',
          localField: 'compound_id',
          foreignField: '_id',
          as: 'compound',
        },
      },
      { $unwind: { path: '$compound', preserveNullAndEmptyArrays: false } },
      {
        $lookup: {
          from: 'developers',
          localField: 'compound.developer_id',
          foreignField: '_id',
          as: 'developer',
        },
      },
      { $unwind: { path: '$developer', preserveNullAndEmptyArrays: false } },
      { $match: { price: { $gt: 0 }, area: { $gt: 0 } } },
      {
        $addFields: {
          price_per_sqm: { $divide: ['$price', '$area'] },
        },
      },
      {
        $group: {
          _id: '$developer.dev_name',
          avg_price_per_sqm: { $avg: '$price_per_sqm' },
          min_price: { $min: '$price' },
          max_price: { $max: '$price' },
          unit_count: { $sum: 1 },
          developer_class: { $first: '$developer.Developer_Class' },
          rating: { $first: '$developer.rating' },
          compounds: { $addToSet: '$compound.name' },
          locations: { $addToSet: '$compound.location' },
        },
      },
      { $match: { _id: { $ne: null } } },
      { $sort: { avg_price_per_sqm: -1 } },
    ];

    const devStats = await db.collection('units').aggregate(devPipeline).toArray();

    const developers = devStats.map((d) => ({
      name: d._id,
      avg_price_per_sqm: Math.round(d.avg_price_per_sqm),
      min_price: Math.round(d.min_price),
      max_price: Math.round(d.max_price),
      unit_count: d.unit_count,
      developer_class: d.developer_class || '',
      rating: d.rating || 0,
      compound_count: d.compounds ? d.compounds.length : 0,
      locations: d.locations ? d.locations.filter((l) => l) : [],
    }));

    // ── 3) Property Type Distribution ──
    const typePipeline = [
      { $match: { price: { $gt: 0 }, area: { $gt: 0 } } },
      {
        $addFields: {
          price_per_sqm: { $divide: ['$price', '$area'] },
          resolved_type: { $ifNull: ['$property_type', { $ifNull: ['$type', 'Other'] }] },
        },
      },
      {
        $group: {
          _id: '$resolved_type',
          avg_price_per_sqm: { $avg: '$price_per_sqm' },
          avg_price: { $avg: '$price' },
          avg_area: { $avg: '$area' },
          count: { $sum: 1 },
        },
      },
      { $match: { _id: { $ne: null } } },
      { $sort: { count: -1 } },
    ];

    const typeStats = await db.collection('units').aggregate(typePipeline).toArray();

    const propertyTypes = typeStats.map((t) => ({
      type: t._id,
      avg_price_per_sqm: Math.round(t.avg_price_per_sqm),
      avg_price: Math.round(t.avg_price),
      avg_area: Math.round(t.avg_area),
      count: t.count,
    }));

    // ── 4) Overall Summary ──
    const totalUnits = areas.reduce((sum, a) => sum + a.unit_count, 0);
    const overallAvg = totalUnits > 0
      ? Math.round(areas.reduce((sum, a) => sum + a.avg_price_per_sqm * a.unit_count, 0) / totalUnits)
      : 0;

    const cheapestArea = areas.length > 0 ? areas[areas.length - 1] : null;
    const expensiveArea = areas.length > 0 ? areas[0] : null;

    return res.json({
      success: true,
      data: {
        areas,
        developers,
        property_types: propertyTypes,
        summary: {
          total_units: totalUnits,
          total_areas: areas.length,
          total_developers: developers.length,
          overall_avg_price_per_sqm: overallAvg,
          cheapest_area: cheapestArea ? cheapestArea.location : '',
          most_expensive_area: expensiveArea ? expensiveArea.location : '',
        },
      },
    });
  } catch (err) {
    console.error('Market analytics error:', err);
    return res.status(500).json({ error: 'Failed to fetch market analytics' });
  }
});

// ─── Price Appraisal (proxy to Python agent) ───
app.post('/appraisal/run', async (req, res) => {
  try {
    // Fix AGENTS_URL if it has /agents/step attached to it
    let agentsBase = process.env.AGENTS_URL || 'https://youssif12-semsai-agents.hf.space';
    if (agentsBase.endsWith('/agents/step')) {
      agentsBase = agentsBase.replace('/agents/step', '');
    }
    const appraisalUrl = `${agentsBase}/appraisal/run`;
    console.log(`[Appraisal] Proxying to: ${appraisalUrl}`);

    const response = await axios.post(appraisalUrl, req.body, {
      timeout: 120000, // 2 min — agent does web scraping
      headers: { 'Content-Type': 'application/json' },
    });
    res.json(response.data);
  } catch (err) {
    console.error('Appraisal proxy error:', err.message);
    res.status(500).json({
      error: 'Failed to run appraisal agent',
      details: err.message,
    });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});