interface Experiment {
  id: string;
  name: string;
  variants: Variant[];
  startTime: number;
  trafficSplit: number;
  targetPath: string;
  status: 'draft' | 'running' | 'paused' | 'completed';
  winner?: string;
}

interface Variant {
  name: string;
  weight: number;
  visitors: number;
  conversions: number;
  customHtml?: string;
}

interface ExperimentRequest {
  name: string;
  variants: Omit<Variant, 'visitors' | 'conversions'>[];
  trafficSplit: number;
  targetPath: string;
}

interface ResultsResponse {
  experiment: Experiment;
  significance?: number;
  confidence?: number;
}

const EXPERIMENTS_KEY = 'ab_experiments';
const COOKIE_PREFIX = 'ab_';

const DEFAULT_STYLES = `
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
      background-color: #0a0a0f; 
      color: #ffffff; 
      line-height: 1.6;
    }
    .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
    header { 
      background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%); 
      padding: 2rem 0; 
      border-bottom: 2px solid #f59e0b;
    }
    h1 { 
      color: #f59e0b; 
      font-size: 2.5rem; 
      margin-bottom: 0.5rem;
      text-align: center;
    }
    .subtitle { 
      color: #a1a1aa; 
      text-align: center; 
      font-size: 1.1rem;
    }
    .card { 
      background: #1a1a2e; 
      border-radius: 10px; 
      padding: 1.5rem; 
      margin: 1rem 0; 
      border: 1px solid #2d2d42;
    }
    .btn { 
      background: #f59e0b; 
      color: #0a0a0f; 
      border: none; 
      padding: 0.75rem 1.5rem; 
      border-radius: 6px; 
      font-weight: 600; 
      cursor: pointer; 
      transition: opacity 0.2s;
    }
    .btn:hover { opacity: 0.9; }
    .btn-secondary { 
      background: #2d2d42; 
      color: #ffffff; 
    }
    .stats-grid { 
      display: grid; 
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
      gap: 1rem; 
      margin: 1.5rem 0;
    }
    .stat { 
      background: #0a0a0f; 
      padding: 1rem; 
      border-radius: 8px; 
      border-left: 4px solid #f59e0b;
    }
    .stat-value { 
      font-size: 2rem; 
      color: #f59e0b; 
      font-weight: 700;
    }
    .stat-label { 
      color: #a1a1aa; 
      font-size: 0.9rem; 
      text-transform: uppercase; 
      letter-spacing: 1px;
    }
    .variant-list { margin: 1.5rem 0; }
    .variant-item { 
      background: #0a0a0f; 
      padding: 1rem; 
      margin: 0.5rem 0; 
      border-radius: 6px; 
      border: 1px solid #2d2d42;
    }
    .winner-badge { 
      background: #10b981; 
      color: white; 
      padding: 0.25rem 0.75rem; 
      border-radius: 12px; 
      font-size: 0.8rem; 
      margin-left: 0.5rem;
    }
    .footer { 
      margin-top: 3rem; 
      padding: 2rem 0; 
      text-align: center; 
      color: #6b7280; 
      border-top: 1px solid #2d2d42;
    }
    .fleet-badge { 
      display: inline-block; 
      background: #f59e0b; 
      color: #0a0a0f; 
      padding: 0.5rem 1rem; 
      border-radius: 20px; 
      font-weight: 600; 
      margin-top: 1rem;
    }
    .form-group { margin: 1rem 0; }
    label { 
      display: block; 
      color: #a1a1aa; 
      margin-bottom: 0.5rem; 
      font-weight: 500;
    }
    input, select { 
      width: 100%; 
      padding: 0.75rem; 
      background: #0a0a0f; 
      border: 1px solid #2d2d42; 
      border-radius: 6px; 
      color: white; 
      font-family: 'Inter', sans-serif;
    }
    .alert { 
      padding: 1rem; 
      border-radius: 6px; 
      margin: 1rem 0;
    }
    .alert-success { background: #064e3b; border-left: 4px solid #10b981; }
    .alert-error { background: #7f1d1d; border-left: 4px solid #ef4444; }
    .nav { 
      display: flex; 
      gap: 1rem; 
      margin: 2rem 0; 
      justify-content: center;
    }
    .nav a { 
      color: #f59e0b; 
      text-decoration: none; 
      padding: 0.5rem 1rem; 
      border-radius: 6px; 
      transition: background 0.2s;
    }
    .nav a:hover { background: #2d2d42; }
    .active { background: #2d2d42; }
  </style>
`;

class ExperimentStore {
  async getExperiments(): Promise<Experiment[]> {
    const data = await EXPERIMENTS.get(EXPERIMENTS_KEY);
    return data ? JSON.parse(data) : [];
  }

  async saveExperiments(experiments: Experiment[]): Promise<void> {
    await EXPERIMENTS.put(EXPERIMENTS_KEY, JSON.stringify(experiments));
  }

  async getExperiment(id: string): Promise<Experiment | null> {
    const experiments = await this.getExperiments();
    return experiments.find(exp => exp.id === id) || null;
  }

  async createExperiment(data: ExperimentRequest): Promise<Experiment> {
    const experiments = await this.getExperiments();
    const experiment: Experiment = {
      id: crypto.randomUUID(),
      name: data.name,
      variants: data.variants.map(v => ({
        ...v,
        visitors: 0,
        conversions: 0
      })),
      startTime: Date.now(),
      trafficSplit: data.trafficSplit,
      targetPath: data.targetPath,
      status: 'draft'
    };
    
    experiments.push(experiment);
    await this.saveExperiments(experiments);
    return experiment;
  }

  async updateExperiment(id: string, updates: Partial<Experiment>): Promise<Experiment | null> {
    const experiments = await this.getExperiments();
    const index = experiments.findIndex(exp => exp.id === id);
    if (index === -1) return null;
    
    experiments[index] = { ...experiments[index], ...updates };
    await this.saveExperiments(experiments);
    return experiments[index];
  }

  async recordVisit(experimentId: string, variantName: string): Promise<void> {
    const experiments = await this.getExperiments();
    const experiment = experiments.find(exp => exp.id === experimentId);
    if (!experiment || experiment.status !== 'running') return;
    
    const variant = experiment.variants.find(v => v.name === variantName);
    if (variant) {
      variant.visitors++;
      await this.saveExperiments(experiments);
    }
  }

  async recordConversion(experimentId: string, variantName: string): Promise<void> {
    const experiments = await this.getExperiments();
    const experiment = experiments.find(exp => exp.id === experimentId);
    if (!experiment || experiment.status !== 'running') return;
    
    const variant = experiment.variants.find(v => v.name === variantName);
    if (variant) {
      variant.conversions++;
      await this.saveExperiments(experiments);
    }
  }
}

class ABTestHandler {
  private store: ExperimentStore;

  constructor() {
    this.store = new ExperimentStore();
  }

  async handleRequest(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === '/health') {
      return new Response(JSON.stringify({ status: 'healthy', timestamp: new Date().toISOString() }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    if (path === '/' || path === '/dashboard') {
      return this.renderDashboard();
    }

    if (path.startsWith('/api/')) {
      return this.handleAPI(request, path);
    }

    const experiments = await this.store.getExperiments();
    const activeExperiment = experiments.find(exp => 
      exp.status === 'running' && 
      exp.targetPath && 
      path.startsWith(exp.targetPath)
    );

    if (activeExperiment && Math.random() * 100 < activeExperiment.trafficSplit) {
      const variant = this.selectVariant(activeExperiment.variants);
      const cookieName = `${COOKIE_PREFIX}${activeExperiment.id}`;
      
      await this.store.recordVisit(activeExperiment.id, variant.name);
      
      const originalResponse = await fetch(request);
      const response = new Response(originalResponse.body, originalResponse);
      
      response.headers.set('Set-Cookie', `${cookieName}=${variant.name}; Path=/; Max-Age=86400`);
      
      if (variant.customHtml && originalResponse.headers.get('Content-Type')?.includes('text/html')) {
        const text = await originalResponse.text();
        const modified = text.replace('</head>', `${variant.customHtml}</head>`);
        return new Response(modified, response);
      }
      
      return response;
    }

    return fetch(request);
  }

  private selectVariant(variants: Variant[]): Variant {
    const totalWeight = variants.reduce((sum, v) => sum + v.weight, 0);
    let random = Math.random() * totalWeight;
    
    for (const variant of variants) {
      if (random < variant.weight) {
        return variant;
      }
      random -= variant.weight;
    }
    
    return variants[0];
  }

  private async handleAPI(request: Request, path: string): Promise<Response> {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      switch (path) {
        case '/api/experiment':
          if (request.method === 'POST') {
            const data: ExperimentRequest = await request.json();
            const experiment = await this.store.createExperiment(data);
            return new Response(JSON.stringify(experiment), {
              headers: { 'Content-Type': 'application/json', ...corsHeaders }
            });
          }
          break;

        case '/api/results':
          if (request.method === 'GET') {
            const url = new URL(request.url);
            const id = url.searchParams.get('id');
            if (!id) {
              const experiments = await this.store.getExperiments();
              return new Response(JSON.stringify(experiments), {
                headers: { 'Content-Type': 'application/json', ...corsHeaders }
              });
            }
            
            const experiment = await this.store.getExperiment(id);
            if (!experiment) {
              return new Response(JSON.stringify({ error: 'Experiment not found' }), {
                status: 404,
                headers: { 'Content-Type': 'application/json', ...corsHeaders }
              });
            }
            
            const results: ResultsResponse = {
              experiment,
              significance: this.calculateSignificance(experiment),
              confidence: this.calculateConfidence(experiment)
            };
            
            return new Response(JSON.stringify(results), {
              headers: { 'Content-Type': 'application/json', ...corsHeaders }
            });
          }
          break;

        case '/api/rollout':
          if (request.method === 'POST') {
            const { id, variant, action } = await request.json();
            
            if (action === 'start') {
              const updated = await this.store.updateExperiment(id, { status: 'running' });
              return new Response(JSON.stringify(updated), {
                headers: { 'Content-Type': 'application/json', ...corsHeaders }
              });
            }
            
            if (action === 'declare-winner') {
              const updated = await this.store.updateExperiment(id, { 
                winner: variant,
                status: 'completed'
              });
              return new Response(JSON.stringify(updated), {
                headers: { 'Content-Type': 'application/json', ...corsHeaders }
              });
            }
            
            if (action === 'pause') {
              const updated = await this.store.updateExperiment(id, { status: 'paused' });
              return new Response(JSON.stringify(updated), {
                headers: { 'Content-Type': 'application/json', ...corsHeaders }
              });
            }
          }
          break;

        case '/api/conversion':
          if (request.method === 'POST') {
            const cookies = request.headers.get('Cookie') || '';
            const experiments = await this.store.getExperiments();
            
            for (const experiment of experiments) {
              if (experiment.status !== 'running') continue;
              
              const cookieName = `${COOKIE_PREFIX}${experiment.id}`;
              const match = cookies.match(new RegExp(`${cookieName}=([^;]+)`));
              
              if (match) {
                await this.store.recordConversion(experiment.id, match[1]);
              }
            }
            
            return new Response(JSON.stringify({ success: true }), {
              headers: { 'Content-Type': 'application/json', ...corsHeaders }
            });
          }
          break;
      }
    } catch (error) {
      return new Response(JSON.stringify({ error: 'Internal server error' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    return new Response(JSON.stringify({ error: 'Not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json', ...corsHeaders }
    });
  }

  private calculateSignificance(experiment: Experiment): number {
    const variants = experiment.variants;
    if (variants.length < 2) return 0;
    
    const control = variants[0];
    const test = variants[1];
    
    if (control.visitors === 0 || test.visitors === 0) return 0;
    
    const controlRate = control.conversions / control.visitors;
    const testRate = test.conversions / test.visitors;
    const pooledRate = (control.conversions + test.conversions) / (control.visitors + test.visitors);
    const se = Math.sqrt(pooledRate * (1 - pooledRate) * (1/control.visitors + 1/test.visitors));
    
    if (se === 0) return 0;
    
    const z = (testRate - controlRate) / se;
    return Math.min(1, Math.max(0, 1 - this.normCDF(Math.abs(z))));
  }

  private calculateConfidence(experiment: Experiment): number {
    const significance = this.calculateSignificance(experiment);
    return Math.round((1 - significance) * 100);
  }

  private normCDF(x: number): number {
    const t = 1 / (1 + 0.2316419 * Math.abs(x));
    const d = 0.3989423 * Math.exp(-x * x / 2);
    let prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
    
    if (x > 0) prob = 1 - prob;
    return prob;
  }

  private async renderDashboard(): Promise<Response> {
    const experiments = await this.store.getExperiments();
    
    const html = `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Fleet A/B Testing</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        ${DEFAULT_STYLES}
      </head>
      <body>
        <header>
          <div class="container">
            <h1>🚀 Fleet A/B Testing</h1>
            <p class="subtitle">Enterprise-grade experimentation platform</p>
            <div class="nav">
              <a href="/dashboard" class="active">Dashboard</a>
              <a href="#create">New Experiment</a>
              <a href="#results">Results</a>
            </div>
          </div>
        </header>
        
        <main class="container">
          <div class="stats-grid">
            <div class="stat">
              <div class="stat-value">${experiments.length}</div>
              <div class="stat-label">Total Experiments</div>
            </div>
            <div class="stat">
              <div class="stat-value">${experiments.filter(e => e.status === 'running').length}</div>
              <div class="stat-label">Active Tests</div>
            </div>
            <div class="stat">
              <div class="stat-value">${experiments.filter(e => e.status === 'completed' && e.winner).length}</div>
              <div class="stat-label">Winners Declared</div>
            </div>
            <div class="stat">
              <div class="stat-value">${experiments.reduce((sum, e) => sum + e.variants.reduce((s, v) => s + v.visitors, 0), 0)}</div>
              <div class="stat-label">Total Visitors</div>
            </div>
          </div>
          
          <div class="card">
            <h2>Create New Experiment</h2>
            <form id="experimentForm">
              <div class="form-group">
                <label for="name">Experiment Name</label>
                <input type="text" id="name" name="name" required placeholder="Homepage Hero Test">
              </div>
              <div class="form-group">
                <label for="targetPath">Target Path</label>
                <input type="text" id="targetPath" name="targetPath" required placeholder="/" value="/">
              </div>
              <div class="form-group">
                <label for="trafficSplit">Traffic Split (%)</label>
                <input type="number" id="trafficSplit" name="trafficSplit" min="1" max="100" value="50">
              </div>
              <div class="form-group">
                <label>Variants</label>
                <div id="variantsContainer">
                  <div class="variant-item">
                    <input type="text" name="variantName[]" placeholder="Control" value="Control" required>
                    <input type="number" name="variantWeight[]" placeholder="Weight" value="50" min="1" max="100" required>
                  </div>
                  <div class="variant-item">
                    <input type="text" name="variantName[]" placeholder="Variant A" value="Variant A" required>
                    <input type="number" name="variantWeight[]" placeholder="Weight" value="50" min="1" max="100" required>
                  </div>
                </div>
                <button type="button" class="btn btn-secondary" onclick="addVariant()">Add Variant</button>
              </div>
              <button type="submit" class="btn">Create Experiment</button>
            </form>
          </div>
          
          <div class="card">
            <h2>Active Experiments</h2>
            <div class="variant-list">
              ${experiments.filter(e => e.status === 'running').map(exp => `
                <div class="variant-item">
                  <h3>${exp.name}</h3>
                  <p>Path: ${exp.targetPath} | Traffic: ${exp.trafficSplit}%</p>
                  <div class="stats-grid">
                    ${exp.variants.map(v => `
                      <div class="stat">
                        <div class="stat-value">${((v.conversions / (v.visitors || 1)) * 100).toFixed(1)}%</div>
                        <div class="stat-label">${v.name} (${v.visitors} visitors)</div>
                      </div>
                    `).join('')}
                  </div>
                  <button class="btn btn-secondary" onclick="declareWinner('${exp.id}', '${exp.variants[1]?.name}')">
                    Declare ${exp.variants[1]?.name} as Winner
                  </button>
                  <button class="btn btn-secondary" onclick="pauseExperiment('${exp.id}')">Pause</button>
                </div>
              `).join('') || '<p>No active experiments</p>'}
            </div>
          </div>
          
          <div class="card">
            <h2>Experiment Results</h2>
            <div class="variant-list">
              ${experiments.map(exp => `
                <div class="variant-item">
                  <h3>${exp.name} 
                    ${exp.winner ? `<span class="winner-badge">Winner:
const sh={"Content-Security-Policy":"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; frame-ancestors 'none'","X-Frame-Options":"DENY"};
export default{async fetch(r:Request){const u=new URL(r.url);if(u.pathname==='/health')return new Response(JSON.stringify({status:'ok'}),{headers:{'Content-Type':'application/json',...sh}});return new Response(html,{headers:{'Content-Type':'text/html;charset=UTF-8',...sh}});}};