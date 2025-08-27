# Build Guide for SpotiVis

## Development

### Quick Start
```bash
# Install dependencies
npm install

# Run everything in watch mode (CSS + TypeScript)
npm run dev

# Then in another terminal, run Flask
flask run
```

### Individual Commands
```bash
# Watch CSS only
npm run dev:css

# Watch TypeScript only  
npm run dev:ts

```

### Development Features
- **Hot Reload**: Changes to TypeScript files auto-rebuild
- **Source Maps**: Inline source maps for debugging
- **No Minification**: Readable output for debugging
- **Fast Rebuilds**: Incremental compilation

## Production

### Build for Production
```bash
# Build everything optimized
npm run build

# Or build individually
npm run build:css  # Minified CSS
npm run build:ts   # Minified, tree-shaken JavaScript
```

### Production Features
- **Minification**: Smaller file sizes
- **Tree Shaking**: Removes unused D3 code
- **No Source Maps**: Smaller builds
- **Optimized**: ~22KB gzipped for combined-graph.js

## File Structure

### Input Files
- TypeScript: `app/typescript/*.ts`
- CSS: `app/static/css/input.css`

### Output Files
- Development:
  - `app/static/js/build/combined-graph.js` (with inline sourcemaps)
  - `app/static/css/output.css`
  
- Production:
  - `app/static/js/build/combined-graph.js` (minified)
  - `app/static/css/output.min.css` (minified)

**Note:** All TypeScript build outputs go to `app/static/js/build/` which is gitignored.

## Workflow

### For Development
1. Run `npm run dev` in one terminal
2. Run `flask run` in another terminal
3. Edit TypeScript files in `app/typescript/`
4. Changes auto-compile and Flask auto-reloads

### For Production Deployment
1. Run `npm run build`
2. Deploy the entire `app/` directory
3. Static files are optimized and ready

## Adding New TypeScript Files

1. Create new `.ts` file in `app/typescript/`
2. Export your functions using ES module syntax:
```typescript
// app/typescript/new-feature.ts
export function myFeature() {
  // Your code here
}
```
3. Build (automatically includes all `.ts` files):
```bash
npm run build:ts
```
4. Import in your template using ES modules:
```html
<script type="module">
  import { myFeature } from "{{ url_for('static', filename='js/build/new-feature.js') }}";
  myFeature();
</script>
```

**Note:** All TypeScript files in `app/typescript/` are automatically built - no config needed!