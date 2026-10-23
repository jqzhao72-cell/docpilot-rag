import { askQuestion, askAgentQuestion } from './chat'

export function requestForMode(mode) {
  return mode === 'agent' ? askAgentQuestion : askQuestion
}
