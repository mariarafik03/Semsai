
import fs from 'fs';
const PROGRESS_FILE = 'e:/StudioProjects/SemsAi/semsai-backend/enrichment_progress.json';
fs.writeFileSync(PROGRESS_FILE, JSON.stringify({ index: 0, data: [] }));
console.log('Progress reset to 0 successfully.');
