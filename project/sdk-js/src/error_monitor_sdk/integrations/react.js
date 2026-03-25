/**
 * React: ошибки рендера ловятся Error Boundary (аналог «middleware» на бэкенде не нужен).
 * Peer: `react`.
 */
const React = require('react');
const { getClient } = require('../index');

/**
 * @typedef {object} MonitorErrorBoundaryProps
 * @property {React.ReactNode} children
 * @property {(error: Error) => React.ReactNode} [fallback]
 * @property {(error: Error, errorInfo: { componentStack?: string }) => void} [onError]
 */

/**
 * @extends {React.Component<MonitorErrorBoundaryProps, { error: Error | null }>}
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

module.exports = {
  MonitorErrorBoundary,
  withMonitorErrorBoundary,
};
