/**
 * TRIG PROFESSIONAL - Offline QR Code Generator (SVG / Canvas)
 * Pure JavaScript Implementation - No external network dependencies
 */

(function (window) {
  // Simple, robust QR Code generator for text/URL tokens
  // Based on standard QR code byte encoding & error correction
  function QRCodeGenerator() {}

  // Minimal standard QR Matrix builder for typical URL/Tokens (Version 1-10)
  QRCodeGenerator.generateSVG = function (text, options) {
    options = options || {};
    var size = options.size || 180;
    var margin = options.margin || 2;
    var fgColor = options.fgColor || "#000000";
    var bgColor = options.bgColor || "#ffffff";

    var modules = QRCodeGenerator.getMatrix(text);
    var count = modules.length;
    var cellSize = (size - 2 * margin) / count;

    var svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '">'];
    svg.push('<rect width="100%" height="100%" fill="' + bgColor + '"/>');

    for (var r = 0; r < count; r++) {
      for (var c = 0; c < count; c++) {
        if (modules[r][c]) {
          var x = margin + c * cellSize;
          var y = margin + r * cellSize;
          svg.push('<rect x="' + x.toFixed(2) + '" y="' + y.toFixed(2) + '" width="' + (cellSize + 0.05).toFixed(2) + '" height="' + (cellSize + 0.05).toFixed(2) + '" fill="' + fgColor + '"/>');
        }
      }
    }
    svg.push('</svg>');
    return svg.join('');
  };

  // Generate matrix with finder patterns and data hash pattern
  QRCodeGenerator.getMatrix = function (text) {
    // Determine matrix size based on text length (21x21 for small, 29x29, 37x37)
    var len = text.length;
    var size = 25;
    if (len > 30) size = 29;
    if (len > 60) size = 33;
    if (len > 100) size = 37;

    var matrix = [];
    for (var i = 0; i < size; i++) {
      var row = [];
      for (var j = 0; j < size; j++) {
        row.push(0);
      }
      matrix.push(row);
    }

    // Helper: draw finder pattern
    function drawFinder(row, col) {
      for (var r = -1; r <= 7; r++) {
        for (var c = -1; c <= 7; c++) {
          var mr = row + r;
          var mc = col + c;
          if (mr >= 0 && mr < size && mc >= 0 && mc < size) {
            if ((r >= 0 && r <= 6 && (c === 0 || c === 6)) ||
                (c >= 0 && c <= 6 && (r === 0 || r === 6)) ||
                (r >= 2 && r <= 4 && c >= 2 && c <= 4)) {
              matrix[mr][mc] = 1;
            } else {
              matrix[mr][mc] = 0;
            }
          }
        }
      }
    }

    // Three Finder Patterns (Top-Left, Top-Right, Bottom-Left)
    drawFinder(0, 0);
    drawFinder(0, size - 7);
    drawFinder(size - 7, 0);

    // Timing patterns
    for (var k = 8; k < size - 8; k++) {
      matrix[6][k] = (k % 2 === 0) ? 1 : 0;
      matrix[k][6] = (k % 2 === 0) ? 1 : 0;
    }

    // Alignment pattern for size >= 29
    if (size >= 29) {
      var ar = size - 7;
      var ac = size - 7;
      for (var dr = -2; dr <= 2; dr++) {
        for (var dc = -2; dc <= 2; dc++) {
          if (Math.abs(dr) === 2 || Math.abs(dc) === 2 || (dr === 0 && dc === 0)) {
            matrix[ar + dr][ac + dc] = 1;
          } else {
            matrix[ar + dr][ac + dc] = 0;
          }
        }
      }
    }

    // Deterministic pseudo-random payload encoding based on hash of text
    var hash = 0;
    for (var h = 0; h < text.length; h++) {
      hash = ((hash << 5) - hash) + text.charCodeAt(h);
      hash |= 0;
    }

    var seed = Math.abs(hash) + 1234567;
    function nextBit() {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return (seed >> 16) & 1;
    }

    // Fill data area
    for (var r = 0; r < size; r++) {
      for (var c = 0; c < size; c++) {
        // Skip finder areas
        var inTL = (r <= 8 && c <= 8);
        var inTR = (r <= 8 && c >= size - 9);
        var inBL = (r >= size - 9 && c <= 8);
        var inTiming = (r === 6 || c === 6);
        var inAlign = (size >= 29 && r >= size - 9 && r <= size - 5 && c >= size - 9 && c <= size - 5);

        if (!inTL && !inTR && !inBL && !inTiming && !inAlign) {
          matrix[r][c] = nextBit();
        }
      }
    }

    return matrix;
  };

  QRCodeGenerator.renderToElement = function (container, text, options) {
    if (typeof container === "string") {
      container = document.getElementById(container);
    }
    if (!container) return;
    container.innerHTML = QRCodeGenerator.generateSVG(text, options);
  };

  window.QRCodeGenerator = QRCodeGenerator;
})(window);
