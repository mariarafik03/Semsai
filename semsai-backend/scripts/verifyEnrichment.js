
import fs from 'fs';
import { parse } from 'csv-parse/sync';

const fileContent = fs.readFileSync('e:/StudioProjects/SemsAi/SemsAi/nawy_enriched.csv', 'utf-8');
const records = parse(fileContent, { columns: true });

const rec = records[0];
console.log('--- ENRICHED DATA VERIFICATION ---');
console.log('Delivery:', rec.delivery_extracted);
console.log('Finishing:', rec.finishing_extracted);
console.log('Lat:', rec.lat_extracted);
console.log('Lng:', rec.lng_extracted);
console.log('Amenities (first 50 chars):', (rec.amenities_extracted || '').substring(0, 50));
console.log('---------------------------------');
