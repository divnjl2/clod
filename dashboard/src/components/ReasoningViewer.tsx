// Reasoning Visualization Components
// dashboard/src/components/ReasoningViewer.tsx

import React, { useState } from 'react';
import {
  Brain, CheckCircle, AlertCircle, TrendingUp,
  ChevronDown, ChevronUp, Lightbulb, Target
} from 'lucide-react';

// ============================================================================
// TYPES
// ============================================================================

interface ThoughtStep {
  step_number: number;
  type: 'understanding' | 'analysis' | 'planning' | 'execution' | 'verification';
  content: string;
  confidence: number;
  alternatives?: string[];
}

interface ReasoningTrace {
  pattern: 'cot' | 'tot' | 'self_consistency' | 'reflection' | 'react';
  thoughts: ThoughtStep[];
  final_answer: string;
  confidence: number;
  verification_passed: boolean;
  reflection?: string;
}

// ============================================================================
// REASONING PATTERN BADGE
// ============================================================================

const PatternBadge: React.FC<{ pattern: string }> = ({ pattern }) => {
  const patternInfo = {
    cot: {
      name: 'Chain-of-Thought',
      color: 'bg-blue-100 text-blue-700',
      icon: '🔗'
    },
    tot: {
      name: 'Tree-of-Thoughts',
      color: 'bg-green-100 text-green-700',
      icon: '🌳'
    },
    self_consistency: {
      name: 'Self-Consistency',
      color: 'bg-purple-100 text-purple-700',
      icon: '🎯'
    },
    reflection: {
      name: 'Reflection',
      color: 'bg-orange-100 text-orange-700',
      icon: '🪞'
    },
    react: {
      name: 'ReAct',
      color: 'bg-pink-100 text-pink-700',
      icon: '⚡'
    }
  };

  const info = patternInfo[pattern as keyof typeof patternInfo];

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium ${info.color}`}>
      <span className="mr-1">{info.icon}</span>
      {info.name}
    </span>
  );
};

// ============================================================================
// THOUGHT STEP COMPONENT
// ============================================================================

const ThoughtStepCard: React.FC<{
  step: ThoughtStep;
  isExpanded: boolean;
  onToggle: () => void;
}> = ({ step, isExpanded, onToggle }) => {
  const typeColors = {
    understanding: 'border-blue-500 bg-blue-50',
    analysis: 'border-purple-500 bg-purple-50',
    planning: 'border-green-500 bg-green-50',
    execution: 'border-orange-500 bg-orange-50',
    verification: 'border-pink-500 bg-pink-50'
  };

  const typeIcons = {
    understanding: '🧐',
    analysis: '🔍',
    planning: '📋',
    execution: '⚙️',
    verification: '✅'
  };

  return (
    <div className={`border-l-4 ${typeColors[step.type]} rounded-r-lg mb-3 overflow-hidden`}>
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-opacity-70"
      >
        <div className="flex items-center space-x-3">
          <span className="text-2xl">{typeIcons[step.type]}</span>
          <div className="text-left">
            <div className="font-semibold text-gray-800">
              Step {step.step_number}: {step.type}
            </div>
            {step.confidence > 0 && (
              <div className="text-xs text-gray-600">
                Confidence: {(step.confidence * 100).toFixed(0)}%
              </div>
            )}
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-gray-500" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-500" />
        )}
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Main Content */}
          <div className="bg-white p-3 rounded border">
            <div className="text-gray-800 whitespace-pre-wrap">{step.content}</div>
          </div>

          {/* Alternatives */}
          {step.alternatives && step.alternatives.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-600 mb-2 flex items-center space-x-1">
                <Lightbulb className="w-3 h-3" />
                <span>Alternatives Considered:</span>
              </div>
              <div className="space-y-2">
                {step.alternatives.map((alt, i) => (
                  <div
                    key={i}
                    className="pl-4 border-l-2 border-gray-300 text-sm text-gray-600"
                  >
                    {alt}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Confidence Bar */}
          {step.confidence > 0 && (
            <div className="mt-2">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-600">Confidence</span>
                <span className="font-semibold">{(step.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    step.confidence > 0.8
                      ? 'bg-green-500'
                      : step.confidence > 0.6
                      ? 'bg-yellow-500'
                      : 'bg-red-500'
                  }`}
                  style={{ width: `${step.confidence * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// QUALITY METRICS
// ============================================================================

const QualityMetrics: React.FC<{ trace: ReasoningTrace }> = ({ trace }) => {
  const metrics = {
    completeness: trace.thoughts.length / 5.0, // Expect ~5 steps
    confidence: trace.confidence,
    depth: trace.thoughts.filter(t => t.alternatives && t.alternatives.length > 0).length / trace.thoughts.length,
    verification: trace.verification_passed ? 1.0 : 0.0
  };

  const overall = Object.values(metrics).reduce((a, b) => a + b, 0) / Object.keys(metrics).length;

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h3 className="font-semibold mb-3 flex items-center space-x-2">
        <TrendingUp className="w-5 h-5 text-blue-600" />
        <span>Quality Metrics</span>
      </h3>

      <div className="space-y-3">
        {/* Overall Score */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium">Overall Quality</span>
            <span className="text-sm font-bold">{(overall * 100).toFixed(0)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className={`h-3 rounded-full ${
                overall > 0.8 ? 'bg-green-500' : overall > 0.6 ? 'bg-yellow-500' : 'bg-red-500'
              }`}
              style={{ width: `${overall * 100}%` }}
            />
          </div>
        </div>

        {/* Individual Metrics */}
        {Object.entries(metrics).map(([key, value]) => (
          <div key={key}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-600 capitalize">{key}</span>
              <span className="text-xs font-semibold">{(value * 100).toFixed(0)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-1.5">
              <div
                className={`h-1.5 rounded-full ${
                  value > 0.8 ? 'bg-green-400' : value > 0.6 ? 'bg-yellow-400' : 'bg-red-400'
                }`}
                style={{ width: `${value * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// MAIN REASONING VIEWER
// ============================================================================

const ReasoningViewer: React.FC<{ trace: ReasoningTrace }> = ({ trace }) => {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set([1]));

  const toggleStep = (stepNumber: number) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(stepNumber)) {
      newExpanded.delete(stepNumber);
    } else {
      newExpanded.add(stepNumber);
    }
    setExpandedSteps(newExpanded);
  };

  return (
    <div className="reasoning-viewer space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Brain className="w-6 h-6 text-purple-600" />
          <h2 className="text-xl font-bold">Reasoning Trace</h2>
        </div>

        <div className="flex items-center space-x-2">
          <PatternBadge pattern={trace.pattern} />
          {trace.verification_passed ? (
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm flex items-center space-x-1">
              <CheckCircle className="w-4 h-4" />
              <span>Verified</span>
            </span>
          ) : (
            <span className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm flex items-center space-x-1">
              <AlertCircle className="w-4 h-4" />
              <span>Not Verified</span>
            </span>
          )}
        </div>
      </div>

      {/* Thinking Steps */}
      <div>
        <h3 className="font-semibold mb-3 flex items-center space-x-2">
          <Brain className="w-5 h-5 text-gray-600" />
          <span>Thinking Process</span>
        </h3>
        <div className="space-y-3">
          {trace.thoughts.map(step => (
            <ThoughtStepCard
              key={step.step_number}
              step={step}
              isExpanded={expandedSteps.has(step.step_number)}
              onToggle={() => toggleStep(step.step_number)}
            />
          ))}
        </div>
      </div>

      {/* Final Answer */}
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-200 rounded-lg p-6">
        <div className="flex items-center space-x-2 mb-3">
          <Target className="w-6 h-6 text-green-600" />
          <h3 className="text-lg font-bold text-green-800">Final Answer</h3>
        </div>
        <div className="text-gray-800 text-lg whitespace-pre-wrap">{trace.final_answer}</div>
        <div className="mt-3 flex items-center justify-between">
          <span className="text-sm text-green-700">
            Confidence: {(trace.confidence * 100).toFixed(0)}%
          </span>
          {trace.verification_passed && (
            <CheckCircle className="w-5 h-5 text-green-600" />
          )}
        </div>
      </div>

      {/* Reflection */}
      {trace.reflection && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-semibold text-blue-800 mb-2">💭 Reflection</h3>
          <p className="text-gray-700">{trace.reflection}</p>
        </div>
      )}

      {/* Quality Metrics */}
      <QualityMetrics trace={trace} />

      {/* Action Buttons */}
      <div className="flex items-center space-x-3">
        <button className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700">
          Save Trace
        </button>
        <button className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50">
          Export JSON
        </button>
        <button className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50">
          Share
        </button>
      </div>
    </div>
  );
};

export default ReasoningViewer;
export { PatternBadge, ThoughtStepCard, QualityMetrics };
