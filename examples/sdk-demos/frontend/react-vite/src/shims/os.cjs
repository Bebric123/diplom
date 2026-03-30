/** Заглушка Node `os` для бандла SDK в браузере */
module.exports = {
  platform: () => 'browser',
  release: () => '',
  hostname: () => 'web',
  arch: () => 'x64',
};
