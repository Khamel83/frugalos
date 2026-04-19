/**
 * Custom processor for Artillery performance testing
 * Provides dynamic test data generation and response validation
 */

module.exports = {
  // Generate random user data
  generateUserData: function(userContext, events, done) {
    const userId = `stress_user_${Math.random().toString(36).substr(2, 9)}`;
    const sessionId = `session_${Math.random().toString(36).substr(2, 9)}`;

    userContext.vars.userId = userId;
    userContext.vars.sessionId = sessionId;
    userContext.vars.timestamp = Date.now();

    return done();
  },

  // Process response and capture metrics
  processResponse: function(requestParams, response, context, ee, done) {
    const responseTime = response.timings.response;
    const statusCode = response.statusCode;

    // Emit custom events for analysis
    ee.emit('customStat', 'response_time', responseTime);

    if (statusCode >= 200 && statusCode < 300) {
      ee.emit('counter', 'successful_requests', 1);
    } else {
      ee.emit('counter', 'failed_requests', 1);
      ee.emit('counter', `error_${statusCode}`, 1);
    }

    // Capture conversation IDs from responses
    if (response.body) {
      try {
        const data = JSON.parse(response.body);
        if (data.data && data.data.conversation_id) {
          context.vars.conversationId = data.data.conversation_id;
        }
      } catch (e) {
        // Ignore JSON parsing errors
      }
    }

    return done();
  },

  // Validate response structure
  validateResponse: function(requestParams, response, context, ee, done) {
    if (response.statusCode !== 200 && response.statusCode !== 201) {
      console.warn(`Unexpected status code: ${response.statusCode}`);
    }

    // Validate response format for API endpoints
    if (response.body) {
      try {
        const data = JSON.parse(response.body);

        // Check for standard API response structure
        if (!data.hasOwnProperty('success')) {
          console.warn('Response missing success field');
        }

        if (!data.hasOwnProperty('timestamp')) {
          console.warn('Response missing timestamp field');
        }

        // Log response size for monitoring
        const responseSize = JSON.stringify(data).length;
        ee.emit('histogram', 'response_size', responseSize);

      } catch (e) {
        console.warn('Invalid JSON response:', e.message);
      }
    }

    return done();
  },

  // Handle errors
  handleError: function(requestParams, error, context, ee, done) {
    console.error('Request error:', error.message);
    ee.emit('counter', 'request_errors', 1);
    return done();
  }
};