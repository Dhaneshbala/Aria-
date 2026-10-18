module.exports = {
  ci: {
    collect: {
      staticDistDir: './dist',
      url: ['http://localhost/index.html'],
    },
    assert: {
      assertions: {
        // Track, don't block: warn if the JS payload regresses past these.
        // (No errors-in-console gate: static serving has no backend, so /api
        // calls 404 by design. Run with backend up for console cleanliness.)
        'resource-summary:script:size': ['warn', { maxNumericValue: 1250000 }],
        'resource-summary:stylesheet:size': ['warn', { maxNumericValue: 150000 }],
      },
    },
    upload: {
      target: 'filesystem',
      outputDir: './.lhci',
    },
  },
}
