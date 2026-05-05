/**
 * React-интеграция (ESM, без require) — для Vite/браузера.
 * Node: require('error-monitor-sdk/integrations/react') → react.js (CJS).
 */
import React from 'react';
import { getClient } from 'error-monitor-sdk';

/**
 * @typedef {object} MonitorErrorBoundaryProps
 * @property {React.ReactNode} children
 * @property {(error: Error) => React.ReactNode} [fallback]
 * @property {(error: Error, errorInfo: { componentStack?: string }) => void} [onError]
 */

class MonitorErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    const client = getClient();
    if (client && typeof window !== 'undefined') {
      client.captureException(
        error,
        {
          source: 'react_error_boundary',
          component_stack: errorInfo.componentStack || '',
        },
        window.location.href,
      );
    }
    if (typeof this.props.onError === 'function') {
      this.props.onError(error, errorInfo);
    }
  }

  render() {
    if (this.state.error) {
      if (typeof this.props.fallback === 'function') {
        return this.props.fallback(this.state.error);
      }
      return null;
    }
    return this.props.children;
  }
}

/**
 * HOC: оборачивает компонент в MonitorErrorBoundary.
 * @param {React.ComponentType<any>} Component
 * @param {Omit<MonitorErrorBoundaryProps, 'children'>} [boundaryProps]
 */
function withMonitorErrorBoundary(Component, boundaryProps = {}) {
  const displayName = Component.displayName || Component.name || 'Component';
  function Wrapped(props) {
    return React.createElement(
      MonitorErrorBoundary,
      boundaryProps,
      React.createElement(Component, props),
    );
  }
  Wrapped.displayName = `withMonitorErrorBoundary(${displayName})`;
  return Wrapped;
}

export { MonitorErrorBoundary, withMonitorErrorBoundary };
