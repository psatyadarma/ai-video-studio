// Build an SVG map snippet from Natural Earth 110m (via mg-styles-15, MIT).
// Usage: node engine/map.mjs "Indonesia" width height [pad] > out.json
import { readFileSync } from 'node:fs';
import { feature } from 'topojson-client';
import { geoMercator, geoPath } from 'd3-geo';
const [name = 'Indonesia', W = 900, H = 500, pad = 0.15] = process.argv.slice(2);
const topo = JSON.parse(readFileSync(new URL('../styles/sticker/data/countries-110m.json', import.meta.url)));
const land = feature(topo, topo.objects.countries);
const target = land.features.find((f) => f.properties.name === name);
const proj = geoMercator().fitExtent([[W * pad, H * pad], [W * (1 - pad), H * (1 - pad)]], target);
const path = geoPath(proj);
const inView = (f) => { const [[x0, y0], [x1, y1]] = path.bounds(f); return x1 > 0 && x0 < W && y1 > 0 && y0 < H && (x1 - x0) < W * 3; };
const others = land.features.filter((f) => f !== target && inView(f)).map((f) => path(f)).filter(Boolean).join(' ');
console.log(JSON.stringify({ W: +W, H: +H, target: path(target), others, centroid: path.centroid(target) }));
