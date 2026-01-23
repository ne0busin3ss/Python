"""
Derivative Visualization: Instantaneous Rate of Change
Dash version with TRUE independent sliders

Requires: dash, plotly, numpy
Install: pip install dash plotly numpy --break-system-packages

Run: python derivative_dash.py
     Then open http://127.0.0.1:8050 in your browser
"""

import numpy as np
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go

# Define function and its derivative
def f(x):
    return x ** 3

def f_prime(x):
    return 3 * x ** 2

# Generate the main curve
x_curve = np.linspace(-0.5, 4.0, 500)
y_curve = f(x_curve)

# Initialize the Dash app
app = Dash(__name__)

app.layout = html.Div([
    html.H1("Derivative Visualization: f(x) = x³", 
            style={'textAlign': 'center', 'color': '#E5E7EB', 'marginBottom': '5px', 'fontFamily': 'system-ui'}),
    
    html.P("Watch the secant line converge to the tangent line as h → 0",
           style={'textAlign': 'center', 'color': '#9CA3AF', 'marginTop': '0', 'fontFamily': 'system-ui'}),
    
    # Main graph
    dcc.Graph(id='derivative-graph', style={'height': '60vh'}),
    
    # Controls container
    html.Div([
        # X position slider
        html.Div([
            html.Label("Point Position (x)", 
                      style={'color': '#EF4444', 'fontWeight': 'bold', 'fontSize': '16px', 'fontFamily': 'system-ui'}),
            dcc.Slider(
                id='x-slider',
                min=0.3,
                max=2.7,
                step=0.05,
                value=1.5,
                marks={i: {'label': str(i), 'style': {'color': '#9CA3AF'}} for i in np.arange(0.5, 3.0, 0.5)},
                tooltip={'placement': 'bottom', 'always_visible': True}
            ),
        ], style={'width': '45%', 'display': 'inline-block', 'padding': '20px', 'verticalAlign': 'top'}),
        
        # H value slider
        html.Div([
            html.Label("Step Size (h)", 
                      style={'color': '#F59E0B', 'fontWeight': 'bold', 'fontSize': '16px', 'fontFamily': 'system-ui'}),
            dcc.Slider(
                id='h-slider',
                min=0.01,
                max=2.0,
                step=0.01,
                value=1.0,
                marks={
                    0.01: {'label': '0.01', 'style': {'color': '#10B981'}},
                    0.1: {'label': '0.1', 'style': {'color': '#9CA3AF'}},
                    0.5: {'label': '0.5', 'style': {'color': '#9CA3AF'}},
                    1.0: {'label': '1.0', 'style': {'color': '#9CA3AF'}},
                    1.5: {'label': '1.5', 'style': {'color': '#9CA3AF'}},
                    2.0: {'label': '2.0', 'style': {'color': '#9CA3AF'}}
                },
                tooltip={'placement': 'bottom', 'always_visible': True}
            ),
        ], style={'width': '45%', 'display': 'inline-block', 'padding': '20px', 'verticalAlign': 'top'}),
    ], style={'backgroundColor': '#1F2937', 'borderRadius': '10px', 'margin': '10px 40px'}),
    
    # Info panel
    html.Div(id='info-panel', style={
        'textAlign': 'center', 
        'padding': '15px', 
        'margin': '10px 40px',
        'backgroundColor': '#1F2937', 
        'borderRadius': '10px',
        'fontFamily': 'monospace'
    }),
    
    # Mathematical explanation
    html.Div([
        html.P([
            html.Strong("Definition: ", style={'color': '#10B981'}),
            "f'(x) = lim",
            html.Sub("h→0"),
            " [f(x+h) − f(x)] / h"
        ], style={'color': '#D1D5DB', 'fontSize': '14px'}),
        html.P([
            html.Strong("For f(x) = x³: ", style={'color': '#3B82F6'}),
            "f'(x) = 3x² (the slope of the tangent line at any point)"
        ], style={'color': '#D1D5DB', 'fontSize': '14px'}),
    ], style={'textAlign': 'center', 'padding': '10px', 'margin': '10px 40px'})
    
], style={'backgroundColor': '#111827', 'minHeight': '100vh', 'padding': '20px'})


@app.callback(
    [Output('derivative-graph', 'figure'),
     Output('info-panel', 'children')],
    [Input('x-slider', 'value'),
     Input('h-slider', 'value')]
)
def update_graph(px, h):
    # Calculate values
    py = f(px)
    slope = f_prime(px)
    
    # Second point
    sx2 = px + h
    sy2 = f(sx2)
    secant_slope = (sy2 - py) / h
    
    # Difference between secant and tangent slopes
    diff = abs(secant_slope - slope)
    
    # Create figure
    fig = go.Figure()
    
    # Main curve
    fig.add_trace(go.Scatter(
        x=x_curve, y=y_curve,
        mode='lines',
        name='f(x) = x³',
        line=dict(color='#3B82F6', width=3),
        hovertemplate='x: %{x:.2f}<br>f(x): %{y:.2f}<extra></extra>'
    ))
    
    # Tangent line (orange, solid)
    tangent_x = np.array([px - 1.5, px + 1.5])
    tangent_y = py + slope * (tangent_x - px)
    fig.add_trace(go.Scatter(
        x=tangent_x, y=tangent_y,
        mode='lines',
        name=f'Tangent (slope = {slope:.3f})',
        line=dict(color='#F59E0B', width=3, dash='solid'),
        hoverinfo='skip'
    ))

    # Secant line (green, dashed)
    secant_x = np.array([px - 0.5, sx2 + 0.5])
    secant_y = py + secant_slope * (secant_x - px)
    fig.add_trace(go.Scatter(
        x=secant_x, y=secant_y,
        mode='lines',
        name=f'Secant (slope = {secant_slope:.3f})',
        line=dict(color='#10B981', width=3, dash='dash'),
        hoverinfo='skip'
    ))
    
    # Delta x (horizontal line)
    fig.add_trace(go.Scatter(
        x=[px, sx2], y=[py, py],
        mode='lines+text',
        name='Δx = h',
        line=dict(color='#F59E0B', width=1.5, dash='dot'),
        text=['', f'Δx={h:.2f}'],
        textposition='bottom center',
        textfont=dict(color='#F59E0B', size=11),
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Delta y (vertical line)
    fig.add_trace(go.Scatter(
        x=[sx2, sx2], y=[py, sy2],
        mode='lines+text',
        name='Δy',
        line=dict(color='#F59E0B', width=1.5, dash='dot'),
        text=['', f'Δy={sy2-py:.2f}'],
        textposition='middle right',
        textfont=dict(color='#F59E0B', size=11),
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Main point (red)
    fig.add_trace(go.Scatter(
        x=[px], y=[py],
        mode='markers',
        name=f'Point ({px:.2f}, {py:.2f})',
        marker=dict(color='#EF4444', size=14, line=dict(color='white', width=2)),
        hovertemplate=f'x = {px:.2f}<br>f(x) = {py:.2f}<br>f\'(x) = {slope:.3f}<extra></extra>'
    ))
    
    # Second point (orange)
    fig.add_trace(go.Scatter(
        x=[sx2], y=[sy2],
        mode='markers',
        name=f'Point ({sx2:.2f}, {sy2:.2f})',
        marker=dict(color='#F59E0B', size=11, line=dict(color='white', width=1.5)),
        hovertemplate=f'x+h = {sx2:.2f}<br>f(x+h) = {sy2:.2f}<extra></extra>'
    ))
    
    # Layout
    fig.update_layout(
        plot_bgcolor='rgba(17,24,39,1)',
        paper_bgcolor='rgba(17,24,39,1)',
        font=dict(color='white'),
        xaxis=dict(
            range=[-0.5, 4.5],
            title='x',
            gridcolor='rgba(128,128,128,0.2)',
            zeroline=True,
            zerolinecolor='rgba(128,128,128,0.5)',
            zerolinewidth=1
        ),
        yaxis=dict(
            range=[-2, 20],
            title='y',
            gridcolor='rgba(128,128,128,0.2)',
            zeroline=True,
            zerolinecolor='rgba(128,128,128,0.5)',
            zerolinewidth=1
        ),
        legend=dict(
            x=0.02, y=0.98,
            bgcolor='rgba(55,65,81,0.9)',
            bordercolor='rgba(75,85,99,1)',
            borderwidth=1,
            font=dict(size=12)
        ),
        margin=dict(l=60, r=40, t=30, b=50),
        hovermode='closest'
    )
    
    # Create info panel content
    convergence_pct = (1 - diff/slope) * 100 if slope != 0 else 100
    
    info_content = [
        html.Div([
            html.Span("Tangent Slope: ", style={'color': '#10B981'}),
            html.Span(f"f'({px:.2f}) = {slope:.4f}", style={'color': '#E5E7EB', 'fontWeight': 'bold'}),
            html.Span("  |  ", style={'color': '#4B5563'}),
            html.Span("Secant Slope: ", style={'color': '#F59E0B'}),
            html.Span(f"Δy/Δx = {secant_slope:.4f}", style={'color': '#E5E7EB', 'fontWeight': 'bold'}),
            html.Span("  |  ", style={'color': '#4B5563'}),
            html.Span("Difference: ", style={'color': '#EF4444'}),
            html.Span(f"|Δ| = {diff:.6f}", style={'color': '#E5E7EB', 'fontWeight': 'bold'}),
        ], style={'fontSize': '14px'}),
        html.Div([
            html.Span(f"Convergence: {convergence_pct:.2f}%", 
                     style={'color': '#10B981' if convergence_pct > 95 else '#F59E0B' if convergence_pct > 80 else '#EF4444',
                           'fontWeight': 'bold', 'fontSize': '16px'})
        ], style={'marginTop': '8px'})
    ]
    
    return fig, info_content


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  DERIVATIVE VISUALIZATION SERVER")
    print("="*60)
    print("\n  → Open your browser to: http://127.0.0.1:8050")
    print("\n  → Press Ctrl+C to stop the server\n")
    app.run(debug=False, host='127.0.0.1', port=8050)
