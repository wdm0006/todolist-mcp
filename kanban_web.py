#!/usr/bin/env python3
# /// script
# dependencies = [
#   "fastapi>=0.104.0",
#   "fastmcp>=2.14.0,<3.0.0",
#   "uvicorn>=0.24.0",
#   "sqlmodel>=0.0.14,<0.1.0",
#   "jinja2>=3.1.0",
#   "python-multipart>=0.0.6",
#   "pytest>=7.0.0",
#   "httpx>=0.24.0",
#   "beautifulsoup4>=4.12.0"
# ]
# ///

"""
FastAPI + HTMX Kanban Board for Todo MCP Server

A modern web interface for the todo database that AI assistants use via MCP.
Features beautiful Jira/Trello-style cards with drag-and-drop functionality.

Usage: uv run kanban_web.py --project-dir /path/to/project
"""

import argparse
import html
import sys
import pathlib
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
from sqlmodel import SQLModel, create_engine, Session, select
from utc_timestamp import utc_now

from todo_mcp import (
    Priority,
    Status,
    Todo,
    TodoDependency as TodoDependency,
    delete_todo_with_dependencies,
    run_migrations,
)


# Global database engine
engine = None


def get_session():
    """Dependency to get database session"""
    with Session(engine) as session:
        yield session


# FastAPI app
app = FastAPI(title="Todo Kanban Board", description="Modern kanban interface for todo management")

# HTML Templates (embedded in code to keep single file)
HTML_BASE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Todo Kanban Board</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/sortablejs@1.15.0/Sortable.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --color-canvas: #F8FAFC;
            --color-surface: #FFFFFF;
            --color-subtle: #F1F5F9;
            --color-border: #E2E8F0;
            --color-text: #0F172A;
            --color-text-muted: #475569;
            --color-primary: #4F46E5;
            --color-primary-hover: #4338CA;
            --color-on-primary: #FFFFFF;
            --color-danger: #E11D48;
            --color-danger-text: #BE123C;
            --color-warning: #F59E0B;
            --color-warning-text: #B45309;
            --color-success: #10B981;
            --color-success-text: #047857;
            --color-backdrop: rgba(15, 23, 42, 0.45);

            --font-sans: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
            --font-mono: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;
            --text-xs: 0.75rem;
            --text-sm: 0.875rem;
            --text-md: 1.125rem;
            --text-lg: 1.25rem;

            --space-1: 0.25rem;
            --space-2: 0.5rem;
            --space-3: 0.75rem;
            --space-4: 1rem;
            --space-6: 1.5rem;
            --space-8: 2rem;

            --radius-sm: 6px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --radius-pill: 999px;

            --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
            --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.03);
            --shadow-hover: 0 10px 15px -3px rgba(0, 0, 0, 0.04);
            --shadow-modal: 0 20px 40px -8px rgba(15, 23, 42, 0.2);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: var(--font-sans);
            background: var(--color-canvas);
            color: var(--color-text);
            font-size: var(--text-sm);
            line-height: 1.5;
            min-height: 100vh;
            overflow-x: auto;
        }

        .header {
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            color: var(--color-text);
            padding: var(--space-6);
            text-align: center;
            box-shadow: var(--shadow-sm);
            margin: var(--space-4);
        }

        .header h1 {
            font-size: var(--text-lg);
            font-weight: 600;
            margin-bottom: var(--space-1);
        }

        .header p {
            font-size: var(--text-sm);
            color: var(--color-text-muted);
            font-weight: 400;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: var(--space-8);
        }

        .controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-8);
            gap: var(--space-4);
            padding: var(--space-4);
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-sm);
        }

        .btn {
            background: var(--color-primary);
            color: var(--color-on-primary);
            border: 1px solid var(--color-primary);
            padding: var(--space-2) var(--space-4);
            border-radius: var(--radius-md);
            font-family: var(--font-sans);
            font-size: var(--text-sm);
            font-weight: 500;
            cursor: pointer;
            transition: background-color 0.15s ease, border-color 0.15s ease;
            text-decoration: none;
            display: inline-block;
        }

        .btn:hover {
            background: var(--color-primary-hover);
            border-color: var(--color-primary-hover);
        }

        .btn-secondary {
            background: var(--color-surface);
            border-color: var(--color-border);
            color: var(--color-text);
        }

        .btn-secondary:hover {
            background: var(--color-subtle);
            border-color: var(--color-border);
        }

        .btn-danger {
            background: var(--color-surface);
            border-color: var(--color-danger);
            color: var(--color-danger-text);
        }

        .btn-danger:hover {
            background: var(--color-subtle);
            border-color: var(--color-danger);
        }

        .kanban-board {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: var(--space-6);
            min-height: 600px;
        }

        .kanban-column {
            background: var(--color-subtle);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            padding: var(--space-4);
        }

        .column-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-4);
        }

        .column-title {
            font-size: var(--text-xs);
            font-weight: 600;
            color: var(--color-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }

        .item-count {
            background: var(--color-surface);
            color: var(--color-text-muted);
            padding: 0 var(--space-2);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-pill);
            font-size: var(--text-xs);
            font-weight: 500;
        }

        .todo-card {
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-md);
            padding: var(--space-3) var(--space-4);
            margin-bottom: var(--space-3);
            box-shadow: var(--shadow-sm);
            cursor: grab;
            transition: box-shadow 0.15s ease;
            position: relative;
        }

        .todo-card:hover {
            box-shadow: var(--shadow-hover);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: var(--space-3);
        }

        .card-title {
            font-weight: 500;
            color: var(--color-text);
            font-size: var(--text-sm);
            line-height: 1.4;
            flex: 1;
            margin-right: var(--space-2);
        }

        .card-id {
            color: var(--color-text-muted);
            font-size: var(--text-xs);
            font-family: var(--font-mono);
        }

        .card-tags {
            display: flex;
            flex-wrap: wrap;
            gap: var(--space-1);
            margin-bottom: var(--space-3);
        }

        .tag {
            padding: 0 var(--space-2);
            border-radius: var(--radius-sm);
            font-size: var(--text-xs);
            color: var(--color-text-muted);
            background-color: var(--color-subtle);
            border: 1px solid var(--color-border);
            font-family: var(--font-mono);
        }

        .card-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .priority-indicator {
            display: flex;
            align-items: center;
            gap: var(--space-2);
            font-size: var(--text-xs);
            color: var(--color-text-muted);
        }

        .priority-dot {
            width: 8px;
            height: 8px;
            border-radius: var(--radius-pill);
        }

        .priority-dot.high { background-color: var(--color-danger); }
        .priority-dot.medium { background-color: var(--color-warning); }
        .priority-dot.low { background-color: var(--color-success); }

        .card-actions {
            display: flex;
            gap: var(--space-2);
            opacity: 0;
            transition: opacity 0.2s ease;
        }

        .todo-card:hover .card-actions,
        .todo-card:focus-within .card-actions {
            opacity: 1;
        }

        .todo-card:focus-visible,
        .btn:focus-visible,
        .btn-sm:focus-visible,
        .form-input:focus-visible,
        .form-select:focus-visible,
        .form-textarea:focus-visible {
            outline: 2px solid var(--color-primary);
            outline-offset: 2px;
        }

        .status-message {
            min-height: 1.25rem;
            margin-top: var(--space-2);
            color: var(--color-text-muted);
            font-size: var(--text-xs);
        }

        .btn-sm {
            padding: var(--space-1) var(--space-2);
            font-size: var(--text-xs);
            background: var(--color-surface);
            color: var(--color-text);
            border: 1px solid var(--color-border);
        }

        .btn-sm:hover {
            background: var(--color-subtle);
            border-color: var(--color-border);
            color: var(--color-danger-text);
        }

        .due-date {
            color: var(--color-text-muted);
            font-size: var(--text-xs);
            margin-bottom: var(--space-2);
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--color-backdrop);
            z-index: 1000;
        }

        .modal.show {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .modal-content {
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            padding: var(--space-6);
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: var(--shadow-modal);
        }

        .modal-content h2 {
            font-size: var(--text-md);
            font-weight: 600;
            margin-bottom: var(--space-4);
        }

        .form-group {
            margin-bottom: var(--space-4);
        }

        .form-label {
            display: block;
            margin-bottom: var(--space-2);
            font-size: var(--text-xs);
            font-weight: 500;
            color: var(--color-text-muted);
        }

        .form-input,
        .form-select,
        .form-textarea {
            width: 100%;
            padding: var(--space-2) var(--space-3);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-md);
            font-size: var(--text-sm);
            background: var(--color-surface);
            color: var(--color-text);
            font-family: var(--font-sans);
        }

        .form-textarea {
            min-height: 100px;
            resize: vertical;
        }

        .form-input:focus,
        .form-select:focus,
        .form-textarea:focus {
            outline: 2px solid var(--color-primary);
            outline-offset: 0;
            border-color: var(--color-primary);
        }

        .sortable-ghost {
            opacity: 0.5;
            border: 1px dashed var(--color-primary);
        }

        .sortable-chosen {
            box-shadow: var(--shadow-hover);
        }

        @media (max-width: 1024px) {
            .kanban-board {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 640px) {
            .kanban-board {
                grid-template-columns: 1fr;
            }

            .container {
                padding: var(--space-4);
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Todo Kanban Board</h1>
        <p>Modern interface for AI assistant project management</p>
    </div>
    
    <div class="container">
        <div class="controls">
            <div>
                <button class="btn" onclick="showCreateModal()">Create New Todo</button>
            </div>
            <div style="display: flex; gap: 1rem; align-items: center;">
                <div>
                    <label class="form-label" style="margin-bottom: 0.25rem; font-size: 0.75rem;">
                        Filter by Priority:
                    </label>
                    <select id="priorityFilter" class="form-select" 
                            style="width: 150px; padding: 0.5rem;" onchange="filterByPriority()">
                        <option value="">All Priorities</option>
                        <option value="high">🔴 High</option>
                        <option value="medium">🟡 Medium</option>
                        <option value="low">🟢 Low</option>
                    </select>
                </div>
                <button class="btn btn-secondary" onclick="location.reload()">Refresh</button>
            </div>
        </div>
        
        <div class="kanban-board" id="kanban-board">
            {{ kanban_content | safe }}
        </div>
    </div>
    
    <!-- Create Todo Modal -->
    <div id="createModal" class="modal">
        <div class="modal-content">
            <h2>Create New Todo</h2>
            <form hx-post="/todos" hx-target="#kanban-board" hx-swap="innerHTML">
                <div class="form-group">
                    <label class="form-label">Description</label>
                    <textarea name="description" class="form-textarea" required 
                              placeholder="What needs to be done?"></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">Detailed Description (Optional)</label>
                    <textarea name="long_description" class="form-textarea" 
                              style="min-height: 120px;" 
                              placeholder="Additional details, requirements, context, or notes..."></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">Priority</label>
                    <select name="priority" class="form-select">
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="low">Low</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Tags</label>
                    <input type="text" name="tags" class="form-input" placeholder="backend,feature,security">
                </div>
                <div class="form-group">
                    <label class="form-label">Due Date</label>
                    <input type="date" name="due_date" class="form-input">
                </div>
                <div style="display: flex; gap: 1rem; justify-content: flex-end;">
                    <button type="button" class="btn btn-secondary" onclick="hideCreateModal()">Cancel</button>
                    <button type="submit" class="btn" onclick="hideCreateModal()">Create Todo</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Detail View Modal -->
    <div id="detailModal" class="modal">
        <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="detailModalTitle">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <h2 id="detailModalTitle"
                    style="margin: 0;">Todo Details</h2>
                <button type="button" class="btn btn-secondary" onclick="hideDetailModal()">Close</button>
            </div>
            <div id="detailContent">
                <!-- Content will be populated by JavaScript -->
            </div>
        </div>
    </div>
    
    <script>
        // Modal functions
        function showCreateModal() {
            document.getElementById('createModal').classList.add('show');
        }
        
        function hideCreateModal() {
            document.getElementById('createModal').classList.remove('show');
        }
        
        // Render persisted todo content as text, never as markup
        function escapeHtml(value) {
            if (value === null || value === undefined) {
                return '';
            }
            return String(value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        // Detail modal functions
        let detailTriggerId = null;

        function showDetailModal(todoId) {
            // Prevent event bubbling from card click
            event.stopPropagation();
            detailTriggerId = todoId;
            
            // Fetch todo details
            fetch(`/todos/${todoId}/details`)
                .then(response => response.json())
                .then(todo => {
                    populateDetailModal(todo);
                    document.getElementById('detailModal').classList.add('show');
                    document.getElementById('detailStatus').focus();
                })
                .catch(error => {
                    console.error('Failed to fetch todo details:', error);
                });
        }
        
        function hideDetailModal() {
            document.getElementById('detailModal').classList.remove('show');
            const card = document.querySelector(`.todo-card[data-todo-id="${detailTriggerId}"]`);
            if (card) {
                card.focus();
            }
        }

        // Cards are role="button": Enter/Space open the modal (ignore keys aimed at the Delete button inside)
        function handleCardKeydown(event, todoId) {
            if (event.target !== event.currentTarget) {
                return;
            }
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                showDetailModal(todoId);
            }
        }

        function changeTodoStatus(todoId, selectEl) {
            const newStatus = selectEl.value;
            const message = document.getElementById('detailStatusMessage');
            const label = selectEl.options[selectEl.selectedIndex].text;
            fetch(`/todos/${todoId}/status`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: `status=${encodeURIComponent(newStatus)}`
            }).then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                message.textContent = `Moved to ${label}.`;
                htmx.ajax('GET', '/kanban-board', {target: '#kanban-board', swap: 'innerHTML'});
            }).catch(error => {
                console.error('Failed to update todo status:', error);
                message.textContent = 'Could not change status. Try again.';
            });
        }
        
        function populateDetailModal(todo) {
            const priorityColors = {
                'high': 'var(--color-danger)',
                'medium': 'var(--color-warning)',
                'low': 'var(--color-success)'
            };
            
            const statusLabels = {
                'open': 'Open',
                'in_progress': 'In Progress',
                'done': 'Done',
                'cancelled': 'Cancelled'
            };
            
            const priorityColor = priorityColors[todo.priority] || 'var(--color-text-muted)';
            const statusOptions = Object.keys(statusLabels).map(value =>
                `<option value="${escapeHtml(value)}"${value === todo.status ? ' selected' : ''}>` +
                `${escapeHtml(statusLabels[value])}</option>`
            ).join('');
            
            // Build tags HTML
            let tagsHtml = '';
            if (todo.tags) {
                const tags = todo.tags.split(',');
                const tagElements = tags.map(tag =>
                    `<span class="tag tag-${escapeHtml(tag.trim().toLowerCase())}">${escapeHtml(tag.trim())}</span>`
                ).join('');
                tagsHtml = `<div style="margin-bottom: 1rem;">
                    <div class="form-label">Tags:</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.25rem;">${tagElements}</div>
                </div>`;
            }
            
            // Build long description HTML
            let longDescHtml = '';
            if (todo.long_description) {
                const longDescText = escapeHtml(todo.long_description);
                longDescHtml = `
                    <div style="margin-bottom: 1rem;">
                        <div class="form-label">Detailed Description:</div>
                        <div style="background: var(--color-subtle); border: 1px solid var(--color-border);
                                     border-radius: var(--radius-md); padding: var(--space-4);
                                     color: var(--color-text); font-family: var(--font-sans);
                                     line-height: 1.5; white-space: pre-wrap;">${longDescText}</div>
                    </div>
                `;
            }
            
            // Build due date HTML
            let dueDateHtml = '';
            if (todo.due_date) {
                const dueDateText = escapeHtml(todo.due_date);
                dueDateHtml = `<div style="margin-bottom: 1rem;">
                    <div class="form-label">Due Date:</div>
                    <div style="color: var(--color-text-muted);">${dueDateText}</div>
                </div>`;
            }
            
            const content = `
                <div style="margin-bottom: 1rem;">
                    <div class="form-label">Task:</div>
                    <div style="color: var(--color-text); font-size: 1.1rem; font-weight: 500;">
                        ${escapeHtml(todo.description)}</div>
                </div>
                
                ${longDescHtml}
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                    <div>
                        <label class="form-label" for="detailStatus">Status:</label>
                        <select id="detailStatus" class="form-select"
                                onchange="changeTodoStatus(${Number(todo.id)}, this)">${statusOptions}</select>
                        <div id="detailStatusMessage" class="status-message" role="status" aria-live="polite"></div>
                    </div>
                    <div>
                        <div class="form-label">Priority:</div>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <div style="width: 8px; height: 8px; border-radius: 999px; 
                                         background: ${priorityColor};"></div>
                            <span style="color: var(--color-text-muted);">${escapeHtml(todo.priority)}</span>
                        </div>
                    </div>
                </div>
                
                ${tagsHtml}
                ${dueDateHtml}
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; 
                             font-size: 0.875rem; color: var(--color-text-muted); margin-top: 1.5rem;">
                    <div>
                        <div class="form-label">Created:</div>
                        <div style="color: var(--color-text-muted); font-size: 0.8rem;">
                            ${new Date(todo.created_at).toLocaleString()}</div>
                    </div>
                    <div>
                        <div class="form-label">Updated:</div>
                        <div style="color: var(--color-text-muted); font-size: 0.8rem;">
                            ${new Date(todo.updated_at).toLocaleString()}
                        </div>
                    </div>
                </div>
                
                <div style="text-align: center; margin-top: 1.5rem; color: var(--color-text-muted); 
                             font-family: var(--font-mono); font-size: 0.8rem;">
                    ID: #${todo.id}
                </div>
            `;
            
            document.getElementById('detailContent').innerHTML = content;
        }
        
        // Priority filtering function
        function filterByPriority() {
            const selectedPriority = document.getElementById('priorityFilter').value;
            const todoCards = document.querySelectorAll('.todo-card');
            
            todoCards.forEach(card => {
                if (selectedPriority === '') {
                    // Show all cards
                    card.style.display = 'block';
                } else {
                    // Check if card has the selected priority class
                    if (card.classList.contains(`priority-${selectedPriority}`)) {
                        card.style.display = 'block';
                    } else {
                        card.style.display = 'none';
                    }
                }
            });
            
            // Update column counts after filtering
            updateColumnCounts();
        }
        
        // Update column counts based on visible cards
        function updateColumnCounts() {
            const columns = document.querySelectorAll('.kanban-column');
            columns.forEach(column => {
                const visibleCards = column.querySelectorAll(
                    '.todo-card[style*="display: block"], .todo-card:not([style*="display: none"])'
                );
                const countElement = column.querySelector('.item-count');
                if (countElement) {
                    countElement.textContent = visibleCards.length;
                }
            });
        }
        
        // Initialize sortable columns
        function initializeSortable() {
            const columns = document.querySelectorAll('.todo-list');
            columns.forEach(column => {
                new Sortable(column, {
                    group: 'todos',
                    animation: 150,
                    ghostClass: 'sortable-ghost',
                    chosenClass: 'sortable-chosen',
                    onEnd: function(evt) {
                        const todoId = evt.item.dataset.todoId;
                        const newStatus = evt.to.dataset.status;
                        
                        // Update todo status via fetch (no HTMX to avoid DOM replacement)
                        fetch(`/todos/${todoId}/status`, {
                            method: 'PUT',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded',
                            },
                            body: `status=${newStatus}`
                        }).catch(error => {
                            console.error('Failed to update todo status:', error);
                            // Optionally revert the drag operation or show error
                        });
                    }
                });
            });
        }
        
        document.addEventListener('DOMContentLoaded', initializeSortable);
        
        // Reinitialize sortable after HTMX updates
        document.body.addEventListener('htmx:afterSwap', function(evt) {
            if (evt.target.id === 'kanban-board') {
                initializeSortable();
                // Reapply priority filter after content update
                filterByPriority();
            }
        });
        
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape' && document.getElementById('detailModal').classList.contains('show')) {
                hideDetailModal();
            }
        });

        // Close modal when clicking outside
        window.onclick = function(event) {
            const createModal = document.getElementById('createModal');
            const detailModal = document.getElementById('detailModal');
            
            if (event.target == createModal) {
                hideCreateModal();
            } else if (event.target == detailModal) {
                hideDetailModal();
            }
        }
    </script>
</body>
</html>
"""


def generate_kanban_html(session: Session) -> str:
    """Generate kanban board HTML"""
    todos = session.exec(select(Todo)).all()

    # Group todos by status
    todos_by_status: dict[Status, list[Todo]] = {
        Status.OPEN: [],
        Status.IN_PROGRESS: [],
        Status.DONE: [],
        Status.CANCELLED: [],
    }

    for todo in todos:
        todos_by_status[todo.status].append(todo)

    # Generate kanban columns HTML
    status_config = {
        Status.OPEN: {"title": "To Do", "class": "open"},
        Status.IN_PROGRESS: {"title": "In Progress", "class": "in-progress"},
        Status.DONE: {"title": "Done", "class": "done"},
        Status.CANCELLED: {"title": "Cancelled", "class": "cancelled"},
    }

    kanban_html = ""
    for status, config in status_config.items():
        todo_cards = ""
        for todo in todos_by_status[status]:
            tags_html = ""
            if todo.tags:
                tags = [tag.strip() for tag in todo.tags.split(",")]
                tag_elements = []
                for tag in tags[:5]:
                    tag_class = (
                        f"tag-{tag.lower()}"
                        if tag.lower()
                        in [
                            "backend",
                            "frontend",
                            "security",
                            "feature",
                            "bugfix",
                            "enhancement",
                            "testing",
                            "docs",
                            "api",
                            "ui",
                            "database",
                            "performance",
                            "refactor",
                        ]
                        else ""
                    )
                    tag_elements.append(f'<span class="tag {tag_class}">{html.escape(tag)}</span>')
                if len(tags) > 5:
                    tag_elements.append(f'<span class="tag">+{len(tags) - 5}</span>')
                tags_html = f'<div class="card-tags">{"".join(tag_elements)}</div>'

            due_date_html = ""
            if todo.due_date:
                due_date_html = f'<div class="due-date">Due: {todo.due_date}</div>'

            todo_cards += f'''
            <div class="todo-card priority-{todo.priority.value}" data-todo-id="{todo.id}"
                 tabindex="0" role="button"
                 aria-label="Open details for task #{todo.id}: {html.escape(todo.description)}"
                 onclick="showDetailModal({todo.id})" onkeydown="handleCardKeydown(event, {todo.id})"
                 style="cursor: pointer;">
                <div class="card-header">
                    <div class="card-title">{html.escape(todo.description)}</div>
                    <div class="card-id">#{todo.id}</div>
                </div>
                {tags_html}
                {due_date_html}
                <div class="card-footer">
                    <div class="priority-indicator">
                        <div class="priority-dot {todo.priority.value}"></div>
                        <span>{todo.priority.value.title()} Priority</span>
                    </div>
                    <div class="card-actions">
                        <button class="btn btn-sm" hx-delete="/todos/{todo.id}" 
                                hx-target="#kanban-board" hx-swap="innerHTML" 
                                hx-confirm="Delete this todo?">Delete</button>
                    </div>
                </div>
            </div>
            '''

        kanban_html += f'''
        <div class="kanban-column">
            <div class="column-header">
                <h2 class="column-title">{config["title"]}</h2>
                <span class="item-count">{len(todos_by_status[status])}</span>
            </div>
            <div class="todo-list" data-status="{status.value}">
                {todo_cards}
            </div>
        </div>
        '''

    return kanban_html


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, session: Session = Depends(get_session)):
    """Main kanban board page"""
    kanban_html = generate_kanban_html(session)

    # Use Jinja2 to render template
    from jinja2 import Template

    template = Template(HTML_BASE)
    return template.render(kanban_content=kanban_html)


@app.get("/kanban-board", response_class=HTMLResponse)
async def get_kanban_board(session: Session = Depends(get_session)):
    """Get just the kanban board HTML for HTMX updates"""
    return generate_kanban_html(session)


@app.post("/todos")
async def create_todo(
    description: str = Form(...),
    priority: Priority = Form(Priority.MEDIUM),
    tags: Optional[str] = Form(None),
    due_date: Optional[str] = Form(None),
    long_description: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """Create a new todo"""
    description = description.strip()
    if not description:
        raise HTTPException(status_code=422, detail="Description cannot be empty.")

    due_date_obj = None
    if due_date:
        try:
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail="Due date must be a valid date in YYYY-MM-DD format.") from None

    todo = Todo(
        description=description,
        long_description=long_description if long_description else None,
        priority=priority,
        tags=tags if tags else None,
        due_date=due_date_obj,
    )

    session.add(todo)
    session.commit()

    # Return redirect to main page after successful creation
    return RedirectResponse(url="/", status_code=303)


@app.put("/todos/{todo_id}/status")
async def update_todo_status(todo_id: int, status: Status = Form(...), session: Session = Depends(get_session)):
    """Update todo status (for drag and drop)"""
    todo = session.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    todo.status = status
    todo.updated_at = utc_now()
    session.add(todo)
    session.commit()

    # Return just a success response - the frontend will handle the UI update
    from fastapi.responses import JSONResponse

    return JSONResponse({"success": True})


@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int, session: Session = Depends(get_session)):
    """Delete a todo"""
    todo = session.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    delete_todo_with_dependencies(session, todo)
    session.commit()

    # Return redirect to main page after successful deletion
    return RedirectResponse(url="/", status_code=303)


@app.get("/todos/{todo_id}/details")
async def get_todo_details(todo_id: int, session: Session = Depends(get_session)):
    """Get detailed information about a specific todo"""
    todo = session.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # Convert to dict with proper date formatting
    todo_dict = {
        "id": todo.id,
        "description": todo.description,
        "long_description": todo.long_description,
        "status": todo.status,
        "priority": todo.priority,
        "tags": todo.tags,
        "due_date": todo.due_date.isoformat() if todo.due_date else None,
        "created_at": todo.created_at.isoformat() if todo.created_at else None,
        "updated_at": todo.updated_at.isoformat() if todo.updated_at else None,
    }

    from fastapi.responses import JSONResponse

    return JSONResponse(todo_dict)


def setup_database(project_dir: Optional[str] = None):
    """Set up database connection"""
    global engine

    if project_dir:
        project_dir_path = pathlib.Path(project_dir).resolve()
        if not project_dir_path.is_dir():
            print(f"Error: Project directory does not exist: {project_dir_path}")
            sys.exit(1)
        database_file = project_dir_path / "todo.db"
    else:
        print("Warning: --project-dir not specified. Using current directory.")
        database_file = pathlib.Path.cwd() / "todo.db"

    database_url = f"sqlite:///{database_file.resolve()}"
    engine = create_engine(database_url)

    # Create tables
    SQLModel.metadata.create_all(engine)

    # Run migrations for existing databases
    run_migrations(engine)

    print(f"Database: {database_file}")
    return database_url


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Todo Kanban Web Interface")
    parser.add_argument("--project-dir", type=str, help="Project directory containing todo.db")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")

    args = parser.parse_args()

    # Setup database
    setup_database(args.project_dir)

    print(f"🚀 Starting Todo Kanban Board at http://{args.host}:{args.port}")
    print("   Press Ctrl+C to stop")

    # Run the server
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
