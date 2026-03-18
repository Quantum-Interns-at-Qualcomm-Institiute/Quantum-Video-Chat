import { resolveHtmlPath } from '../../main/util';

describe('resolveHtmlPath', () => {
  const originalEnv = process.env.NODE_ENV;

  afterEach(() => {
    process.env.NODE_ENV = originalEnv;
  });

  it('returns localhost URL in development', () => {
    process.env.NODE_ENV = 'development';
    const result = resolveHtmlPath('index.html');
    expect(result).toContain('localhost');
    expect(result).toContain('index.html');
  });

  it('uses PORT env var in development', () => {
    process.env.NODE_ENV = 'development';
    const originalPort = process.env.PORT;
    process.env.PORT = '3456';
    const result = resolveHtmlPath('index.html');
    expect(result).toContain('3456');
    process.env.PORT = originalPort;
  });

  it('returns file:// path in production', () => {
    process.env.NODE_ENV = 'production';
    const result = resolveHtmlPath('index.html');
    expect(result).toMatch(/^file:\/\//);
  });
});
