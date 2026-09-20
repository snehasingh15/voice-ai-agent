/**
 * useResilientWebSocket - Enterprise-grade WebSocket hook
 *
 * Features:
 * - Exponential backoff reconnection (1s -> 2s -> 4s -> 8s, capped at 15s)
 * - Heartbeat ping/pong every 25s to keep Render free-tier and Nginx proxies alive
 * - Tracks reconnect attempt count and exposes status for UI display
 */

import { useCallback, useEffect, useRef, useState } from 'react'

const HEARTBEAT_INTERVAL_MS = 25_000   // send ping every 25s
const MAX_BACKOFF_MS        = 15_000   // cap reconnect delay at 15s
const INITIAL_BACKOFF_MS    = 1_000   // first reconnect after 1s

/**
 * @param {string} url - WebSocket URL (wss:// or ws://)
 * @param {object} handlers
 * @param {(event: MessageEvent) => void} handlers.onMessage
 * @param {() => void}                   handlers.onOpen
 * @param {() => void}                   handlers.onClose
 * @returns {{ send, close, readyState, reconnectAttempts }}
 */
export function useResilientWebSocket(url, { onMessage, onOpen, onClose } = {}) {
  const wsRef               = useRef(null)
  const heartbeatRef        = useRef(null)
  const reconnectTimerRef   = useRef(null)
  const backoffRef          = useRef(INITIAL_BACKOFF_MS)
  const isMountedRef        = useRef(true)
  const onMessageRef        = useRef(onMessage)
  const onOpenRef           = useRef(onOpen)
  const onCloseRef          = useRef(onClose)
  const [readyState, setReadyState]             = useState(WebSocket.CONNECTING)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)

  // Keep handler refs fresh without triggering re-connect
  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])
  useEffect(() => { onOpenRef.current = onOpen }, [onOpen])
  useEffect(() => { onCloseRef.current = onClose }, [onClose])

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current)
      heartbeatRef.current = null
    }
  }, [])

  const startHeartbeat = useCallback((ws) => {
    stopHeartbeat()
    heartbeatRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, HEARTBEAT_INTERVAL_MS)
  }, [stopHeartbeat])

  const connect = useCallback(() => {
    if (!isMountedRef.current) return

    const ws = new WebSocket(url)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      if (!isMountedRef.current) return
      backoffRef.current = INITIAL_BACKOFF_MS  // reset backoff on success
      setReadyState(WebSocket.OPEN)
      setReconnectAttempts(0)
      startHeartbeat(ws)
      onOpenRef.current?.()
    }

    ws.onmessage = (event) => {
      // Swallow pong frames silently
      if (typeof event.data === 'string') {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'pong') return  // heartbeat pong, no action needed
        } catch { /* binary or non-JSON: pass through */ }
      }
      onMessageRef.current?.(event)
    }

    ws.onerror = () => {
      // onerror always fires before onclose; just let onclose handle reconnect
    }

    ws.onclose = (event) => {
      if (!isMountedRef.current) return
      stopHeartbeat()
      setReadyState(WebSocket.CLOSED)
      onCloseRef.current?.()

      // Schedule reconnect with exponential backoff
      const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS)
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS)
      setReconnectAttempts((n) => n + 1)

      reconnectTimerRef.current = setTimeout(() => {
        if (isMountedRef.current) connect()
      }, delay)
    }

    setReadyState(WebSocket.CONNECTING)
  }, [url, startHeartbeat, stopHeartbeat])

  // Mount / unmount
  useEffect(() => {
    isMountedRef.current = true
    connect()
    return () => {
      isMountedRef.current = false
      stopHeartbeat()
      clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect, stopHeartbeat])

  const send = useCallback((data) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(data)
      return true
    }
    return false
  }, [])

  const close = useCallback(() => {
    isMountedRef.current = false
    stopHeartbeat()
    clearTimeout(reconnectTimerRef.current)
    wsRef.current?.close()
  }, [stopHeartbeat])

  return { send, close, readyState, reconnectAttempts, wsRef }
}
