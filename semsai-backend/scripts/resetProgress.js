
import fs from 'fs';
const PROGRESS_FILE = 'e:/StudioProjects/SemsAi/semsai-backend/enrichment_progress.json';
if (fs.existsSync(PROGRESS_FILE)) {
    const progress = JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf-8'));
    progress.index = 540; // Manually reset to 540 as per user request/safety
    // Trim data to match index
    progress.data = progress.data.slice(0, 540);
    fs.writeFileSync(PROGRESS_FILE, JSON.stringify(progress));
    console.log('Progress reset to index 540 successfully.');
}
