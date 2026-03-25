/**
 * Отправка хвоста лог-файла на POST /logs/upload (Node.js).
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const axios = require('axios');

/**
 * @param {object} client — экземпляр MonitorClient (endpoint, projectId, context, debug)
 * @param {string} filepath
 * @param {object} [options]
 * @param {number} [options.lines=50]
 * @param {string} [options.serverName]
 * @param {string} [options.serviceName]
 * @param {string} [options.environment]
 * @param {string} [options.errorGroupId]
 * @returns {boolean} false если файла нет или он пустой
 */
function sendLogFile(client, filepath, options = {}) {
  if (!client || !client.endpoint) {
    throw new Error('Invalid monitor client');
  }

  const lines = options.lines != null ? options.lines : 50;

  if (!fs.existsSync(filepath)) {
    return false;
  }

  let raw;
  try {
    raw = fs.readFileSync(filepath, { encoding: 'utf8' });
  } catch {
    return false;
  }

  const allLines = raw.split(/\r?\n/);
  const totalLines = allLines.length;
  const take = lines > 0 ? Math.min(lines, totalLines) : totalLines;
  const slice = totalLines <= take ? allLines : allLines.slice(-take);
  const content = slice.join('\n');

  if (!content.trim()) {
    return false;
  }

  const filename = path.basename(filepath);
  const payload = {
    project_id: client.projectId,
    filename,
    content,
    lines_sent: take,
    total_lines: totalLines,
    server_name: options.serverName ?? os.hostname(),
    service_name: options.serviceName ?? null,
    environment:
      options.environment ??
      (client.context && client.context.environment) ??
      'production',
    error_group_id: options.errorGroupId ?? null,
  };

  setImmediate(() => {
    axios
      .post(`${client.endpoint.replace(/\/$/, '')}/logs/upload`, payload, {
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'ErrorMonitor-SDK/1.0 (Node.js logs)',
        },
        timeout: 10000,
      })
      .then((res) => {
        if (client.debug) {
          console.log('[MonitorSDK] Log upload OK', res.data);
        }
      })
      .catch((err) => {
        const msg =
          err.response?.data != null
            ? JSON.stringify(err.response.data)
            : err.message;
        console.error('[MonitorSDK] Log upload failed:', msg);
      });
  });

  return true;
}

module.exports = { sendLogFile };
