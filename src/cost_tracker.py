"""
Cost Tracker for OpenAI API usage.
Tracks token usage and estimates costs in real-time.
"""

from typing import Dict, Optional
import logging


logger = logging.getLogger(__name__)


class CostTracker:
    """Tracks API costs in real-time."""
    
    PRICES = {
        'gpt-4o-mini': {
            'input': 0.00015 / 1000,   # per token
            'output': 0.0006 / 1000
        },
        'gpt-4o': {
            'input': 0.005 / 1000,
            'output': 0.015 / 1000
        },
        'gpt-4-turbo': {
            'input': 0.01 / 1000,
            'output': 0.03 / 1000
        }
    }
    
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
        self.by_step = {}
    
    def track_call(self, response, step: str = 'unknown') -> Dict:
        """Track tokens from OpenAI response."""
        try:
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.call_count += 1
            
            # Track by step
            if step not in self.by_step:
                self.by_step[step] = {'input': 0, 'output': 0, 'calls': 0}
            self.by_step[step]['input'] += input_tokens
            self.by_step[step]['output'] += output_tokens
            self.by_step[step]['calls'] += 1
            
            return {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens
            }
        except AttributeError:
            logger.warning("Could not extract usage from response")
            return {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
    
    def get_total_cost(self, model: str = 'gpt-4o-mini') -> float:
        """Calculate total cost based on model pricing."""
        if model not in self.PRICES:
            logger.warning(f"Unknown model {model}, using gpt-4o-mini pricing")
            model = 'gpt-4o-mini'
        
        prices = self.PRICES[model]
        input_cost = self.total_input_tokens * prices['input']
        output_cost = self.total_output_tokens * prices['output']
        return input_cost + output_cost
    
    def report(self, model: str = 'gpt-4o-mini') -> str:
        """Generate cost report."""
        total_cost = self.get_total_cost(model)
        
        report = f"""
💰 COST REPORT ({model}):
{'='*40}
API Calls: {self.call_count:,}
Input Tokens: {self.total_input_tokens:,}
Output Tokens: {self.total_output_tokens:,}
Total Tokens: {self.total_input_tokens + self.total_output_tokens:,}
{'='*40}
TOTAL COST: ${total_cost:.4f}
"""
        
        if self.by_step:
            report += "\n📊 BY STEP:\n"
            for step, data in self.by_step.items():
                step_cost = (data['input'] * self.PRICES[model]['input'] + 
                           data['output'] * self.PRICES[model]['output'])
                report += f"  {step}: {data['calls']} calls, ${step_cost:.4f}\n"
        
        return report
    
    def reset(self) -> None:
        """Reset all counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
        self.by_step = {}

    def to_dict(self, model: str = 'gpt-4o-mini') -> Dict:
        """Convert current state to dictionary for persistence."""
        from datetime import datetime
        return {
            'timestamp': datetime.now().isoformat(),
            'model': model,
            'call_count': self.call_count,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_cost_usd': self.get_total_cost(model),
            'steps': self.by_step
        }
    
    def export_to_csv(self, path: str = 'logs/cost_metrics.csv', model: str = 'gpt-4o-mini') -> str:
        """
        Export metrics to CSV for historical tracking.
        Appends to existing file if it exists.
        """
        import csv
        import os
        from datetime import datetime
        from pathlib import Path
        
        Path('logs').mkdir(exist_ok=True)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'model': model,
            'call_count': self.call_count,
            'input_tokens': self.total_input_tokens,
            'output_tokens': self.total_output_tokens,
            'total_cost_usd': round(self.get_total_cost(model), 6)
        }
        
        file_exists = os.path.exists(path)
        
        with open(path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(data)
        
        logger.info(f"📊 Metrics exported to {path}")
        return path
