const path = require('path');

module.exports = {
  entry: './src/error_monitor_sdk/index.js',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'error-monitor-sdk.js',
    library: 'ErrorMonitor',
    libraryTarget: 'umd',
    globalObject: 'this',
  },
  mode: 'production',
};