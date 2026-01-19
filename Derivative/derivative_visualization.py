"""
Derivative Visualization: Instantaneous Rate of Change
Interactive exploration of tangent and secant lines for f(x) = x²

Requires: matplotlib, numpy
Install: pip install matplotlib numpy

Run: python derivative_visualization.py
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, CheckButtons

# Define function and its derivative
def f(x):
    return x ** 2

def f_prime(x):
    return 2 * x

# Set up the figure and axis
fig, ax = plt.subplots(figsize=(12, 8))
plt.subplots_adjust(left=0.08, right=0.75, bottom=0.38, top=0.93)  # Make room for sliders and text

# Plot settings
x_min, x_max = -1, 4
y_min, y_max = -1, 10
ax.set_xlim(x_min, x_max)
ax.set_ylim(y_min, y_max)
ax.set_xlabel('x', fontsize=12)
ax.set_ylabel('y', fontsize=12)
ax.set_title('The Derivative: Instantaneous Rate of Change\nf(x) = x²  →  f\'(x) = 2x', fontsize=14)
ax.grid(True, alpha=0.3)
ax.set_aspect('equal', adjustable='box')
ax.axhline(y=0, color='gray', linewidth=0.8)
ax.axvline(x=0, color='gray', linewidth=0.8)

# Generate curve
x_curve = np.linspace(x_min, x_max, 500)
y_curve = f(x_curve)
curve_line, = ax.plot(x_curve, y_curve, 'b-', linewidth=2.5, label='f(x) = x²')

# Initial values
init_point_x = 1.5
init_h = 1.0

# Calculate initial values
point_y = f(init_point_x)
slope = f_prime(init_point_x)

# Tangent line (extends beyond the point)
tangent_x = np.array([init_point_x - 1.5, init_point_x + 1.5])
tangent_y = point_y + slope * (tangent_x - init_point_x)
tangent_line, = ax.plot(tangent_x, tangent_y, 'g-', linewidth=2, 
                         label=f'Tangent (slope = {slope:.2f})')

# Secant line
secant_x2 = init_point_x + init_h
secant_y2 = f(secant_x2)
secant_slope = (secant_y2 - point_y) / init_h
secant_x = np.array([init_point_x - 0.5, secant_x2 + 0.5])
secant_y = point_y + secant_slope * (secant_x - init_point_x)
secant_line, = ax.plot(secant_x, secant_y, '--', color='orange', linewidth=2, 
                        label=f'Secant (slope = {secant_slope:.2f})')

# Delta x and delta y lines (showing rise over run)
delta_x_line, = ax.plot([init_point_x, secant_x2], [point_y, point_y], 
                         ':', color='orange', linewidth=1.5, alpha=0.7)
delta_y_line, = ax.plot([secant_x2, secant_x2], [point_y, secant_y2], 
                         ':', color='orange', linewidth=1.5, alpha=0.7)

# Points
main_point, = ax.plot(init_point_x, point_y, 'ro', markersize=12, 
                       markeredgecolor='white', markeredgewidth=2, zorder=5)
second_point, = ax.plot(secant_x2, secant_y2, 'o', color='orange', markersize=8, 
                         markeredgecolor='white', markeredgewidth=1.5, zorder=5)

# Text annotations (positioned to the right of the plot area)
info_text = fig.text(0.85, 0.65, '', fontsize=9,
                     verticalalignment='top', fontfamily='monospace',
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

def update_info_text(px, py, slope, h, secant_slope, show_secant):
    text = f'Point:  x = {px:.2f}, f(x) = {py:.2f}\n'
    text += f'f\'(x) = 2x = {slope:.2f} (tangent slope)\n'
    if show_secant and h > 0.05:
        text += f'h = {h:.2f}, secant slope = {secant_slope:.2f}\n'
        text += f'Difference: {abs(secant_slope - slope):.4f}'
    info_text.set_text(text)

update_info_text(init_point_x, point_y, slope, init_h, secant_slope, True)

# Legend
ax.legend(loc='upper right')

# --- Sliders ---

# Slider for point x position
ax_point_x = plt.axes([0.15, 0.25, 0.55, 0.03])
slider_point_x = Slider(ax_point_x, 'Point x', 0.2, 3.0, valinit=init_point_x, color='red')

# Slider for h (secant distance)
ax_h = plt.axes([0.15, 0.19, 0.55, 0.03])
slider_h = Slider(ax_h, 'h (→0 for derivative)', 0.01, 2.0, valinit=init_h, color='orange')

# Checkbox for secant line visibility
ax_check = plt.axes([0.15, 0.10, 0.12, 0.06])
check_secant = CheckButtons(ax_check, ['Show Secant'], [True])

# Track secant visibility
show_secant = [True]

def update(val):
    # Get current values
    px = slider_point_x.val
    h = slider_h.val
    
    # Calculate new values
    py = f(px)
    slope = f_prime(px)
    
    # Update main point
    main_point.set_data([px], [py])
    
    # Update tangent line
    new_tangent_x = np.array([px - 1.5, px + 1.5])
    new_tangent_y = py + slope * (new_tangent_x - px)
    tangent_line.set_data(new_tangent_x, new_tangent_y)
    tangent_line.set_label(f'Tangent (slope = {slope:.2f})')
    
    # Update secant line
    sx2 = px + h
    sy2 = f(sx2)
    secant_slope = (sy2 - py) / h if h > 0.001 else slope
    
    new_secant_x = np.array([px - 0.3, sx2 + 0.3])
    new_secant_y = py + secant_slope * (new_secant_x - px)
    secant_line.set_data(new_secant_x, new_secant_y)
    secant_line.set_label(f'Secant (slope = {secant_slope:.2f})')
    
    # Update second point and delta lines
    second_point.set_data([sx2], [sy2])
    delta_x_line.set_data([px, sx2], [py, py])
    delta_y_line.set_data([sx2, sx2], [py, sy2])
    
    # Update visibility based on checkbox
    visible = show_secant[0]
    secant_line.set_visible(visible)
    second_point.set_visible(visible)
    delta_x_line.set_visible(visible)
    delta_y_line.set_visible(visible)
    
    # Update info text
    update_info_text(px, py, slope, h, secant_slope, visible)
    
    # Update legend
    ax.legend(loc='upper right')
    
    fig.canvas.draw_idle()

def toggle_secant(label):
    show_secant[0] = not show_secant[0]
    update(None)

# Connect callbacks
slider_point_x.on_changed(update)
slider_h.on_changed(update)
check_secant.on_clicked(toggle_secant)

# Key insight annotation
insight_text = """
KEY INSIGHT: As h → 0, the secant line approaches the tangent line.
The derivative f'(x) = lim[h→0] (f(x+h) - f(x)) / h
Drag the 'h' slider left to see this convergence!
"""
fig.text(0.5, 0.01, insight_text, ha='center', fontsize=9, 
         style='italic', color='darkgreen',
         bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.3))

plt.show()
