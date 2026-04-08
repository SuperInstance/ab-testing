typescript
export interface Env {
  EXPERIMENTS: KVNamespace;
}

interface Experiment {
  id: string;
  name: string;
  description: string;
  variants: Variant[];
  trafficSplit: number; // Percentage to experiment (0-100)
  createdAt: number;
  status: 'active' | 'paused' | 'ended';
}

interface Variant {
  name: string;
  weight: number; // Percentage (0-100)
  cssSelector: string;
  htmlModification: string;
  metrics: {
    views: number;
    conversions: number;
  };
}

interface ExperimentResult {
  experiment: Experiment;
  totals: {
    views: number;
    conversions: number;
  };
  variants: Array<Variant & {
    conversionRate: number;
    improvement: number;
  }>;
}

class ExperimentManager {
  constructor(private kv: KVNamespace) {}

  async createExperiment(experiment: Omit<Experiment, 'id' | 'createdAt' | 'status'>): Promise<Experiment> {
    const id = `exp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const fullExperiment: Experiment = {
      ...experiment,
      id,
      createdAt: Date.now(),
      status: 'active'
    };
    
    await this.kv.put(`experiment:${id}`, JSON.stringify(fullExperiment));
    return fullExperiment;
  }

  async getExperiment(id: string): Promise<Experiment | null> {
    const data = await this.kv.get(`experiment:${id}`);
    return data ? JSON.parse(data) : null;
  }

  async getAllExperiments(): Promise<Experiment[]> {
    const list = await this.kv.list({ prefix: 'experiment:' });
    const experiments: Experiment[] = [];
    
    for (const key of list.keys) {
      const data = await this.kv.get(key.name);
      if (data) {
        experiments.push(JSON.parse(data));
      }
    }
    
    return experiments;
  }

  async assignVariant(experimentId: string, request: Request): Promise<string | null> {
    const experiment = await this.getExperiment(experimentId);
    if (!experiment || experiment.status !== 'active') return null;

    // Use consistent hashing based on IP + User-Agent
    const ip = request.headers.get('cf-connecting-ip') || '';
    const ua = request.headers.get('user-agent') || '';
    const hash = this.hashString(`${ip}:${ua}:${experimentId}`);
    
    // Check if user falls into experiment traffic
    if (hash % 100 >= experiment.trafficSplit) return null;

    // Weighted random variant selection
    const totalWeight = experiment.variants.reduce((sum, v) => sum + v.weight, 0);
    let random = hash % totalWeight;
    
    for (const variant of experiment.variants) {
      if (random < variant.weight) {
        await this.recordView(experimentId, variant.name);
        return variant.name;
      }
      random -= variant.weight;
    }
    
    return null;
  }

  async recordView(experimentId: string, variantName: string): Promise<void> {
    const experiment = await this.getExperiment(experimentId);
    if (!experiment) return;

    const variantIndex = experiment.variants.findIndex(v => v.name === variantName);
    if (variantIndex === -1) return;

    experiment.variants[variantIndex].metrics.views++;
    await this.kv.put(`experiment:${experimentId}`, JSON.stringify(experiment));
  }

  async recordConversion(experimentId: string, variantName: string): Promise<void> {
    const experiment = await this.getExperiment(experimentId);
    if (!experiment) return;

    const variantIndex = experiment.variants.findIndex(v => v.name === variantName);
    if (variantIndex === -1) return;

    experiment.variants[variantIndex].metrics.conversions++;
    await this.kv.put(`experiment:${experimentId}`, JSON.stringify(experiment));
  }

  async getResults(experimentId: string): Promise<ExperimentResult | null> {
    const experiment = await this.getExperiment(experimentId);
    if (!experiment) return null;

    const totals = {
      views: experiment.variants.reduce((sum, v) => sum + v.metrics.views, 0),
      conversions: experiment.variants.reduce((sum, v) => sum + v.metrics.conversions, 0)
    };

    const controlVariant = experiment.variants[0];
    const controlRate = controlVariant.metrics.views > 0 
      ? (controlVariant.metrics.conversions / controlVariant.metrics.views) * 100 
      : 0;

    const variants = experiment.variants.map(variant => {
      const conversionRate = variant.metrics.views > 0 
        ? (variant.metrics.conversions / variant.metrics.views) * 100 
        : 0;
      
      const improvement = controlRate > 0 
        ? ((conversionRate - controlRate) / controlRate) * 100 
        : 0;

      return {
        ...variant,
        conversionRate: parseFloat(conversionRate.toFixed(2)),
        improvement: parseFloat(improvement.toFixed(2))
      };
    });

    return {
      experiment,
      totals,
      variants
    };
  }

  private hashString(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash);
  }
}

const HTML_TEMPLATE = (content: string, experimentScript?: string) => `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fleet A/B Testing</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
      background: #0a0a0f; 
      color: #e2e8f0; 
      line-height: 1.6; 
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    .container { 
      max-width: 1200px; 
      margin: 0 auto; 
      padding: 2rem; 
      flex: 1;
    }
    header { 
      border-bottom: 1px solid #1e293b; 
      padding-bottom: 1rem; 
      margin-bottom: 2rem; 
    }
    h1 { 
      color: #f59e0b; 
      font-size: 2.5rem; 
      margin-bottom: 0.5rem; 
    }
    .subtitle { 
      color: #94a3b8; 
      font-size: 1.1rem; 
    }
    .card { 
      background: #1a1a2e; 
      border-radius: 8px; 
      padding: 1.5rem; 
      margin-bottom: 1.5rem; 
      border: 1px solid #2d3748; 
    }
    .card h2 { 
      color: #f59e0b; 
      margin-bottom: 1rem; 
      font-size: 1.5rem; 
    }
    .btn { 
      background: #f59e0b; 
      color: #0a0a0f; 
      border: none; 
      padding: 0.75rem 1.5rem; 
      border-radius: 4px; 
      font-weight: 600; 
      cursor: pointer; 
      transition: opacity 0.2s; 
      text-decoration: none; 
      display: inline-block; 
    }
    .btn:hover { opacity: 0.9; }
    .btn-secondary { 
      background: #2d3748; 
      color: #e2e8f0; 
    }
    .form-group { 
      margin-bottom: 1rem; 
    }
    label { 
      display: block; 
      margin-bottom: 0.5rem; 
      color: #cbd5e1; 
      font-weight: 500; 
    }
    input, textarea, select { 
      width: 100%; 
      padding: 0.75rem; 
      background: #0f172a; 
      border: 1px solid #334155; 
      border-radius: 4px; 
      color: #e2e8f0; 
      font-family: inherit; 
    }
    .variant-row { 
      display: flex; 
      gap: 1rem; 
      margin-bottom: 1rem; 
      align-items: flex-end; 
    }
    .variant-row input { 
      flex: 1; 
    }
    .variant-row .weight { 
      width: 100px; 
    }
    .metrics-grid { 
      display: grid; 
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
      gap: 1rem; 
      margin-top: 1rem; 
    }
    .metric-card { 
      background: #0f172a; 
      padding: 1rem; 
      border-radius: 6px; 
      border-left: 4px solid #f59e0b; 
    }
    .metric-value { 
      font-size: 2rem; 
      font-weight: 700; 
      color: #f59e0b; 
    }
    .metric-label { 
      color: #94a3b8; 
      font-size: 0.9rem; 
      margin-top: 0.25rem; 
    }
    .improvement-positive { color: #10b981; }
    .improvement-negative { color: #ef4444; }
    footer { 
      background: #0f172a; 
      padding: 2rem; 
      text-align: center; 
      border-top: 1px solid #1e293b; 
      margin-top: auto; 
    }
    .footer-content { 
      max-width: 1200px; 
      margin: 0 auto; 
      color: #94a3b8; 
    }
    .footer-logo { 
      color: #f59e0b; 
      font-weight: 700; 
      font-size: 1.2rem; 
      margin-bottom: 0.5rem; 
    }
    .health-status { 
      display: inline-block; 
      width: 10px; 
      height: 10px; 
      background: #10b981; 
      border-radius: 50%; 
      margin-right: 0.5rem; 
    }
    .experiment-list { 
      display: grid; 
      gap: 1rem; 
    }
    .experiment-item { 
      display: flex; 
      justify-content: space-between; 
      align-items: center; 
      padding: 1rem; 
      background: #0f172a; 
      border-radius: 6px; 
      border-left: 4px solid #f59e0b; 
    }
    .status-badge { 
      padding: 0.25rem 0.75rem; 
      border-radius: 20px; 
      font-size: 0.875rem; 
      font-weight: 500; 
    }
    .status-active { background: #065f46; color: #6ee7b7; }
    .status-paused { background: #92400e; color: #fbbf24; }
    .status-ended { background: #1e293b; color: #94a3b8; }
  </style>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
  <div class="container">
    <header>
      <h1>Fleet A/B Testing</h1>
      <div class="subtitle">Cloudflare Worker-based experimentation platform</div>
    </header>
    ${content}
  </div>
  <footer>
    <div class="footer-content">
      <div class="footer-logo">Fleet A/B Testing Platform</div>
      <div>Built with Cloudflare Workers • Zero Dependencies • Global Edge Network</div>
      <div style="margin-top: 1rem; font-size: 0.875rem;">
        <span class="health-status"></span> System Operational
      </div>
    </div>
  </footer>
  ${experimentScript || ''}
</body>
</html>`;
const sh={"Content-Security-Policy":"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; frame-ancestors 'none'","X-Frame-Options":"DENY"};
export default{async fetch(r:Request){const u=new URL(r.url);if(u.pathname==='/health')return new Response(JSON.stringify({status:'ok'}),{headers:{'Content-Type':'application/json',...sh}});return new Response(html,{headers:{'Content-Type':'text/html;charset=UTF-8',...sh}});}};