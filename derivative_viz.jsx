import React, { useState } from 'react';

export default function DerivativeVisualization() {
  const [pointX, setPointX] = useState(1.5);
  const [showSecant, setShowSecant] = useState(true);
  const [h, setH] = useState(1.5);
  
  // Function: f(x) = x^2
  const f = (x) => x * x;
  const fPrime = (x) => 2 * x; // derivative
  
  // SVG dimensions
  const width = 600;
  const height = 450;
  const padding = 50;
  
  // Scale functions
  const xMin = -1, xMax = 4;
  const yMin = -1, yMax = 10;
  
  const scaleX = (x) => padding + ((x - xMin) / (xMax - xMin)) * (width - 2 * padding);
  const scaleY = (y) => height - padding - ((y - yMin) / (yMax - yMin)) * (height - 2 * padding);
  
  // Generate curve points
  const curvePoints = [];
  for (let x = xMin; x <= xMax; x += 0.05) {
    const y = f(x);
    if (y >= yMin && y <= yMax) {
      curvePoints.push(`${scaleX(x)},${scaleY(y)}`);
    }
  }
  
  // Point on curve
  const pointY = f(pointX);
  const slope = fPrime(pointX);
  
  // Secant line second point
  const secantX2 = pointX + h;
  const secantY2 = f(secantX2);
  const secantSlope = (secantY2 - pointY) / h;
  
  // Tangent line endpoints
  const tangentX1 = pointX - 1.5;
  const tangentY1 = pointY + slope * (tangentX1 - pointX);
  const tangentX2 = pointX + 1.5;
  const tangentY2 = pointY + slope * (tangentX2 - pointX);
  
  // Secant line endpoints
  const secLineX1 = pointX - 0.5;
  const secLineY1 = pointY + secantSlope * (secLineX1 - pointX);
  const secLineX2 = secantX2 + 0.5;
  const secLineY2 = pointY + secantSlope * (secLineX2 - pointX);

  return (
    <div className="p-6 bg-gray-900 min-h-screen text-white">
      <h1 className="text-2xl font-bold mb-2 text-center">The Derivative: Instantaneous Rate of Change</h1>
      <p className="text-center text-gray-400 mb-4">f(x) = x² → f'(x) = 2x</p>
      
      <div className="flex flex-col items-center">
        <svg width={width} height={height} className="bg-gray-800 rounded-lg">
          {/* Grid */}
          {[-1, 0, 1, 2, 3, 4].map(x => (
            <line key={`vgrid-${x}`} x1={scaleX(x)} y1={scaleY(yMin)} x2={scaleX(x)} y2={scaleY(yMax)} 
                  stroke="#374151" strokeWidth="1" />
          ))}
          {[0, 2, 4, 6, 8, 10].map(y => (
            <line key={`hgrid-${y}`} x1={scaleX(xMin)} y1={scaleY(y)} x2={scaleX(xMax)} y2={scaleY(y)} 
                  stroke="#374151" strokeWidth="1" />
          ))}
          
          {/* Axes */}
          <line x1={scaleX(xMin)} y1={scaleY(0)} x2={scaleX(xMax)} y2={scaleY(0)} stroke="#9CA3AF" strokeWidth="2" />
          <line x1={scaleX(0)} y1={scaleY(yMin)} x2={scaleX(0)} y2={scaleY(yMax)} stroke="#9CA3AF" strokeWidth="2" />
          
          {/* Axis labels */}
          {[1, 2, 3].map(x => (
            <text key={`xlabel-${x}`} x={scaleX(x)} y={scaleY(0) + 20} fill="#9CA3AF" textAnchor="middle" fontSize="12">{x}</text>
          ))}
          {[2, 4, 6, 8].map(y => (
            <text key={`ylabel-${y}`} x={scaleX(0) - 15} y={scaleY(y) + 4} fill="#9CA3AF" textAnchor="middle" fontSize="12">{y}</text>
          ))}
          
          {/* Curve f(x) = x² */}
          <polyline points={curvePoints.join(' ')} fill="none" stroke="#3B82F6" strokeWidth="3" />
          
          {/* Secant line (if enabled and h > 0.1) */}
          {showSecant && h > 0.1 && (
            <>
              <line x1={scaleX(secLineX1)} y1={scaleY(secLineY1)} 
                    x2={scaleX(secLineX2)} y2={scaleY(secLineY2)} 
                    stroke="#F59E0B" strokeWidth="2" strokeDasharray="8,4" />
              {/* Second point */}
              <circle cx={scaleX(secantX2)} cy={scaleY(secantY2)} r="6" fill="#F59E0B" />
              {/* Delta x and delta y visualization */}
              <line x1={scaleX(pointX)} y1={scaleY(pointY)} x2={scaleX(secantX2)} y2={scaleY(pointY)} 
                    stroke="#F59E0B" strokeWidth="1" strokeDasharray="4,2" />
              <line x1={scaleX(secantX2)} y1={scaleY(pointY)} x2={scaleX(secantX2)} y2={scaleY(secantY2)} 
                    stroke="#F59E0B" strokeWidth="1" strokeDasharray="4,2" />
              <text x={scaleX(pointX + h/2)} y={scaleY(pointY) + 15} fill="#F59E0B" textAnchor="middle" fontSize="11">h = {h.toFixed(2)}</text>
            </>
          )}
          
          {/* Tangent line */}
          <line x1={scaleX(tangentX1)} y1={scaleY(tangentY1)} 
                x2={scaleX(tangentX2)} y2={scaleY(tangentY2)} 
                stroke="#10B981" strokeWidth="2.5" />
          
          {/* Point on curve */}
          <circle cx={scaleX(pointX)} cy={scaleY(pointY)} r="8" fill="#EF4444" stroke="white" strokeWidth="2" />
          
          {/* Labels */}
          <text x={width - 60} y={30} fill="#3B82F6" fontSize="14" fontWeight="bold">f(x) = x²</text>
          <text x={20} y={30} fill="#10B981" fontSize="13">Tangent (slope = {slope.toFixed(2)})</text>
          {showSecant && h > 0.1 && (
            <text x={20} y={50} fill="#F59E0B" fontSize="13">Secant (slope = {secantSlope.toFixed(2)})</text>
          )}
        </svg>
        
        {/* Info panel */}
        <div className="mt-4 bg-gray-800 p-4 rounded-lg w-full max-w-lg">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-400">Point x = </span>
              <span className="text-red-400 font-mono">{pointX.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-gray-400">f(x) = </span>
              <span className="text-blue-400 font-mono">{pointY.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-gray-400">f'(x) = 2x = </span>
              <span className="text-green-400 font-mono">{slope.toFixed(2)}</span>
            </div>
            {showSecant && h > 0.1 && (
              <div>
                <span className="text-gray-400">Secant slope = </span>
                <span className="text-yellow-400 font-mono">{secantSlope.toFixed(2)}</span>
              </div>
            )}
          </div>
          
          {showSecant && h > 0.1 && (
            <div className="mt-3 text-xs text-gray-500 border-t border-gray-700 pt-2">
              As h → 0, secant slope ({secantSlope.toFixed(2)}) → tangent slope ({slope.toFixed(2)})
            </div>
          )}
        </div>
        
        {/* Controls */}
        <div className="mt-4 space-y-3 w-full max-w-lg">
          <div>
            <label className="text-sm text-gray-400 block mb-1">Move point along curve (x)</label>
            <input 
              type="range" 
              min="0.5" 
              max="2.5" 
              step="0.1" 
              value={pointX} 
              onChange={(e) => setPointX(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input 
                type="checkbox" 
                checked={showSecant} 
                onChange={(e) => setShowSecant(e.target.checked)}
                className="w-4 h-4"
              />
              <span className="text-gray-300">Show secant line</span>
            </label>
          </div>
          
          {showSecant && (
            <div>
              <label className="text-sm text-gray-400 block mb-1">
                Adjust h (distance to second point): {h.toFixed(2)}
              </label>
              <input 
                type="range" 
                min="0.05" 
                max="2" 
                step="0.05" 
                value={h} 
                onChange={(e) => setH(parseFloat(e.target.value))}
                className="w-full"
              />
              <p className="text-xs text-gray-500 mt-1">
                Drag left to see secant approach tangent (h → 0)
              </p>
            </div>
          )}
        </div>
        
        {/* Key insight box */}
        <div className="mt-6 bg-gradient-to-r from-blue-900/50 to-green-900/50 p-4 rounded-lg w-full max-w-lg border border-blue-700">
          <h3 className="font-semibold text-blue-300 mb-2">Key Insight</h3>
          <p className="text-sm text-gray-300">
            The derivative f'(x) = 2x tells us the slope at <em>any</em> point. At x = {pointX.toFixed(1)}, 
            the tangent line has slope {slope.toFixed(2)}, meaning for tiny movements, 
            y changes about {slope.toFixed(2)}× as fast as x.
          </p>
        </div>
      </div>
    </div>
  );
}
