#!/usr/bin/env python3
# /// script
# dependencies = [
#   "fastapi>=0.104.0",
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
import sys
import pathlib
from datetime import datetime, date
from typing import Dict, List, Optional
from enum import Enum

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from sqlmodel import SQLModel, Field, create_engine, Session, select

# Enumerations for Todo status and priority
class Status(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress" 
    DONE = "done"
    CANCELLED = "cancelled"

class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

# SQLModel for Todo items
class Todo(SQLModel, table=True, extend_existing=True):
    """Todo item model"""
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str = Field(index=True)
    status: Status = Field(default=Status.OPEN, index=True)
    priority: Priority = Field(default=Priority.MEDIUM, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    due_date: Optional[date] = Field(default=None, index=True)
    tags: Optional[str] = Field(default=None, index=True)

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
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            background: #0a0a0a;
            background-image: 
                radial-gradient(circle at 20% 80%, #001a2e 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, #1a0033 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, #000a1a 0%, transparent 50%);
            color: #00ff41;
            line-height: 1.6;
            min-height: 100vh;
            position: relative;
            overflow-x: auto;
        }
        
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                repeating-linear-gradient(
                    0deg,
                    transparent,
                    transparent 2px,
                    rgba(0, 255, 65, 0.03) 2px,
                    rgba(0, 255, 65, 0.03) 4px
                );
            pointer-events: none;
            z-index: 1;
        }
        
        .header {
            background: linear-gradient(135deg, #001122, #000033);
            border: 2px solid #00ff41;
            border-radius: 0;
            color: #00ff41;
            padding: 2rem;
            text-align: center;
            box-shadow: 
                0 0 20px rgba(0, 255, 65, 0.3),
                inset 0 0 20px rgba(0, 255, 65, 0.1);
            position: relative;
            z-index: 2;
            margin: 1rem;
            text-transform: uppercase;
        }
        
        .header::before {
            content: '> ';
            color: #ff0080;
            font-weight: bold;
        }
        
        .header::after {
            content: ' <';
            color: #ff0080;
            font-weight: bold;
        }
        
        .header h1 {
            font-family: 'Orbitron', monospace;
            font-size: 2.5rem;
            font-weight: 900;
            margin-bottom: 0.5rem;
            text-shadow: 
                0 0 10px #00ff41,
                0 0 20px #00ff41,
                0 0 30px #00ff41;
            letter-spacing: 0.1em;
        }
        
        .header p {
            opacity: 0.8;
            font-size: 1rem;
            color: #00ccff;
            text-shadow: 0 0 5px #00ccff;
            font-weight: 400;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
            position: relative;
            z-index: 2;
        }
        
        .controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            gap: 1rem;
            padding: 1rem;
            background: rgba(0, 20, 40, 0.8);
            border: 1px solid #00ff41;
            border-radius: 0;
            box-shadow: 0 0 10px rgba(0, 255, 65, 0.2);
        }
        
        .btn {
            background: linear-gradient(135deg, #001a33, #002244);
            color: #00ff41;
            border: 2px solid #00ff41;
            padding: 0.75rem 1.5rem;
            border-radius: 0;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            position: relative;
            overflow: hidden;
        }
        
        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 65, 0.2), transparent);
            transition: left 0.5s;
        }
        
        .btn:hover {
            background: linear-gradient(135deg, #002244, #003355);
            box-shadow: 
                0 0 20px rgba(0, 255, 65, 0.5),
                inset 0 0 20px rgba(0, 255, 65, 0.1);
            transform: translateY(-2px);
            color: #ffffff;
        }
        
        .btn:hover::before {
            left: 100%;
        }
        
        .btn-secondary {
            background: linear-gradient(135deg, #330066, #440088);
            border-color: #ff0080;
            color: #ff0080;
        }
        
        .btn-secondary:hover {
            background: linear-gradient(135deg, #440088, #5500aa);
            box-shadow: 
                0 0 20px rgba(255, 0, 128, 0.5),
                inset 0 0 20px rgba(255, 0, 128, 0.1);
            color: #ffffff;
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #330000, #440000);
            border-color: #ff0040;
            color: #ff0040;
        }
        
        .btn-danger:hover {
            background: linear-gradient(135deg, #440000, #550000);
            box-shadow: 
                0 0 20px rgba(255, 0, 64, 0.5),
                inset 0 0 20px rgba(255, 0, 64, 0.1);
            color: #ffffff;
        }
        
        .kanban-board {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 2rem;
            min-height: 600px;
        }
        
        .kanban-column {
            background: linear-gradient(135deg, rgba(0, 20, 40, 0.9), rgba(0, 30, 60, 0.8));
            border: 2px solid #00ff41;
            border-radius: 0;
            padding: 1.5rem;
            box-shadow: 
                0 0 20px rgba(0, 255, 65, 0.3),
                inset 0 0 20px rgba(0, 255, 65, 0.05);
            position: relative;
        }
        
        .kanban-column::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #ff0080, #00ff41, #00ccff);
            animation: pulse 2s ease-in-out infinite alternate;
        }
        
        .column-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid #00ff41;
            position: relative;
        }
        
        .column-header::before {
            content: '[';
            color: #ff0080;
            font-weight: bold;
            margin-right: 0.5rem;
        }
        
        .column-header::after {
            content: ']';
            color: #ff0080;
            font-weight: bold;
            margin-left: 0.5rem;
        }
        
        .column-title {
            font-family: 'Orbitron', monospace;
            font-size: 1.25rem;
            font-weight: 700;
            color: #00ff41;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            text-shadow: 0 0 10px #00ff41;
        }
        
        .item-count {
            background: linear-gradient(135deg, #ff0080, #ff0040);
            color: #ffffff;
            padding: 0.25rem 0.75rem;
            border: 1px solid #ff0080;
            border-radius: 0;
            font-size: 0.875rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            box-shadow: 0 0 10px rgba(255, 0, 128, 0.5);
            text-shadow: 0 0 5px #ffffff;
        }
        
        .todo-card {
            background: linear-gradient(135deg, rgba(0, 0, 0, 0.8), rgba(0, 20, 40, 0.6));
            border: 1px solid #00ccff;
            border-radius: 0;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 
                0 0 15px rgba(0, 204, 255, 0.3),
                inset 0 0 15px rgba(0, 204, 255, 0.1);
            cursor: grab;
            transition: all 0.3s ease;
            position: relative;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .todo-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border: 1px solid transparent;
            background: linear-gradient(45deg, #00ccff, #ff0080, #00ff41) border-box;
            -webkit-mask: linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: exclude;
            mask: linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0);
            mask-composite: exclude;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .todo-card:hover {
            box-shadow: 
                0 0 25px rgba(0, 204, 255, 0.6),
                inset 0 0 25px rgba(0, 204, 255, 0.2);
            transform: translateY(-2px) scale(1.02);
        }
        
        .todo-card:hover::before {
            opacity: 1;
        }
        
        .todo-card.priority-high {
            border-left: 4px solid #ff0040;
            box-shadow: 
                0 0 15px rgba(255, 0, 64, 0.4),
                inset 0 0 15px rgba(255, 0, 64, 0.1);
        }
        
        .todo-card.priority-medium {
            border-left: 4px solid #ffaa00;
            box-shadow: 
                0 0 15px rgba(255, 170, 0, 0.4),
                inset 0 0 15px rgba(255, 170, 0, 0.1);
        }
        
        .todo-card.priority-low {
            border-left: 4px solid #00ff41;
            box-shadow: 
                0 0 15px rgba(0, 255, 65, 0.4),
                inset 0 0 15px rgba(0, 255, 65, 0.1);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.75rem;
        }
        
        .card-title {
            font-weight: 500;
            color: #00ff41;
            font-size: 0.9rem;
            line-height: 1.4;
            flex: 1;
            margin-right: 0.5rem;
            text-shadow: 0 0 5px rgba(0, 255, 65, 0.3);
        }
        
        .card-id {
            color: #00ccff;
            font-size: 0.75rem;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
            text-shadow: 0 0 3px rgba(0, 204, 255, 0.5);
        }
        
        .card-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.25rem;
            margin-bottom: 0.75rem;
        }
        
        .tag {
            padding: 0.125rem 0.5rem;
            border-radius: 0;
            font-size: 0.75rem;
            font-weight: 500;
            color: #000;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border: 1px solid;
            box-shadow: 0 0 5px rgba(0, 255, 65, 0.3);
            position: relative;
        }
        
        .tag::before {
            content: '[';
            margin-right: 0.2em;
            color: inherit;
        }
        
        .tag::after {
            content: ']';
            margin-left: 0.2em;
            color: inherit;
        }
        
        .tag-backend { background-color: #00ff41; border-color: #00ff41; color: #000; }
        .tag-frontend { background-color: #00ccff; border-color: #00ccff; color: #000; }
        .tag-security { background-color: #ff0040; border-color: #ff0040; color: #fff; }
        .tag-feature { background-color: #00ff80; border-color: #00ff80; color: #000; }
        .tag-bugfix { background-color: #ffaa00; border-color: #ffaa00; color: #000; }
        .tag-enhancement { background-color: #ff0080; border-color: #ff0080; color: #fff; }
        .tag-testing { background-color: #80ff00; border-color: #80ff00; color: #000; }
        .tag-docs { background-color: #666666; border-color: #666666; color: #fff; }
        .tag-api { background-color: #0080ff; border-color: #0080ff; color: #fff; }
        .tag-ui { background-color: #ff8000; border-color: #ff8000; color: #000; }
        .tag-database { background-color: #40ff00; border-color: #40ff00; color: #000; }
        .tag-performance { background-color: #ffff00; border-color: #ffff00; color: #000; }
        .tag-refactor { background-color: #8000ff; border-color: #8000ff; color: #fff; }
        .tag:not([class*="tag-"]) { background-color: #666666; border-color: #666666; color: #fff; }
        
        .card-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .priority-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
            color: #00ccff;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .priority-dot {
            width: 8px;
            height: 8px;
            border-radius: 0;
            border: 1px solid;
            box-shadow: 0 0 5px;
        }
        
        .priority-dot.high { 
            background-color: #ff0040; 
            border-color: #ff0040; 
            box-shadow: 0 0 5px #ff0040;
        }
        .priority-dot.medium { 
            background-color: #ffaa00; 
            border-color: #ffaa00; 
            box-shadow: 0 0 5px #ffaa00;
        }
        .priority-dot.low { 
            background-color: #00ff41; 
            border-color: #00ff41; 
            box-shadow: 0 0 5px #00ff41;
        }
        
        .card-actions {
            display: flex;
            gap: 0.5rem;
            opacity: 0;
            transition: opacity 0.2s ease;
        }
        
        .todo-card:hover .card-actions {
            opacity: 1;
        }
        
        .btn-sm {
            padding: 0.25rem 0.5rem;
            font-size: 0.75rem;
            border-radius: 0;
            background: linear-gradient(135deg, #001122, #002244);
            color: #00ff41;
            border: 1px solid #00ff41;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            box-shadow: 0 0 5px rgba(0, 255, 65, 0.2);
        }
        
        .btn-sm:hover {
            background: linear-gradient(135deg, #002244, #003366);
            box-shadow: 0 0 10px rgba(0, 255, 65, 0.4);
            color: #ffffff;
        }
        
        .due-date {
            color: #ff0080;
            font-size: 0.75rem;
            margin-bottom: 0.5rem;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            text-shadow: 0 0 3px rgba(255, 0, 128, 0.5);
        }
        
        .due-date::before {
            content: '> ';
            color: #00ccff;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
        }
        
        .modal.show {
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .modal-content {
            background: linear-gradient(135deg, rgba(0, 10, 20, 0.95), rgba(0, 20, 40, 0.9));
            border: 2px solid #00ff41;
            border-radius: 0;
            padding: 2rem;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 
                0 0 30px rgba(0, 255, 65, 0.3),
                inset 0 0 30px rgba(0, 255, 65, 0.1);
            position: relative;
        }
        
        .modal-content::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #ff0080, #00ff41, #00ccff);
            animation: pulse 2s ease-in-out infinite alternate;
        }
        
        .form-group {
            margin-bottom: 1rem;
        }
        
        .form-label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
            color: #00ff41;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            text-shadow: 0 0 5px rgba(0, 255, 65, 0.3);
        }
        
        .form-label::before {
            content: '> ';
            color: #ff0080;
        }
        
        .form-input {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #00ccff;
            border-radius: 0;
            font-size: 0.875rem;
            background: rgba(0, 10, 20, 0.8);
            color: #00ff41;
            font-family: 'JetBrains Mono', monospace;
            box-shadow: 0 0 10px rgba(0, 204, 255, 0.2);
        }
        
        .form-input:focus {
            outline: none;
            border-color: #00ff41;
            box-shadow: 
                0 0 15px rgba(0, 255, 65, 0.4),
                inset 0 0 10px rgba(0, 255, 65, 0.1);
        }
        
        .form-select {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #00ccff;
            border-radius: 0;
            font-size: 0.875rem;
            background: rgba(0, 10, 20, 0.8);
            color: #00ff41;
            font-family: 'JetBrains Mono', monospace;
            box-shadow: 0 0 10px rgba(0, 204, 255, 0.2);
        }
        
        .form-select:focus {
            outline: none;
            border-color: #00ff41;
            box-shadow: 
                0 0 15px rgba(0, 255, 65, 0.4),
                inset 0 0 10px rgba(0, 255, 65, 0.1);
        }
        
        .form-textarea {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #00ccff;
            border-radius: 0;
            font-size: 0.875rem;
            min-height: 100px;
            resize: vertical;
            background: rgba(0, 10, 20, 0.8);
            color: #00ff41;
            font-family: 'JetBrains Mono', monospace;
            box-shadow: 0 0 10px rgba(0, 204, 255, 0.2);
        }
        
        .form-textarea:focus {
            outline: none;
            border-color: #00ff41;
            box-shadow: 
                0 0 15px rgba(0, 255, 65, 0.4),
                inset 0 0 10px rgba(0, 255, 65, 0.1);
        }
        
        .sortable-ghost {
            opacity: 0.5;
            border: 2px dashed #00ff41;
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.5);
        }
        
        .sortable-chosen {
            transform: rotate(2deg) scale(1.05);
            box-shadow: 
                0 0 25px rgba(0, 255, 65, 0.6),
                inset 0 0 25px rgba(0, 255, 65, 0.2);
        }
        
        @keyframes pulse {
            0% { opacity: 0.8; }
            100% { opacity: 1; }
        }
        
        @keyframes glitch {
            0%, 100% { transform: translateX(0); }
            20% { transform: translateX(-2px); }
            40% { transform: translateX(2px); }
            60% { transform: translateX(-1px); }
            80% { transform: translateX(1px); }
        }
        
        .header h1:hover {
            animation: glitch 0.3s ease-in-out;
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
                padding: 1rem;
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
                    <label class="form-label" style="margin-bottom: 0.25rem; font-size: 0.75rem;">Filter by Priority:</label>
                    <select id="priorityFilter" class="form-select" style="width: 150px; padding: 0.5rem;" onchange="filterByPriority()">
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
                    <textarea name="description" class="form-textarea" required placeholder="What needs to be done?"></textarea>
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
    
    <script>
        // Modal functions
        function showCreateModal() {
            document.getElementById('createModal').classList.add('show');
        }
        
        function hideCreateModal() {
            document.getElementById('createModal').classList.remove('show');
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
                const visibleCards = column.querySelectorAll('.todo-card[style*="display: block"], .todo-card:not([style*="display: none"])');
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
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('createModal');
            if (event.target == modal) {
                hideCreateModal();
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
    todos_by_status = {
        Status.OPEN: [],
        Status.IN_PROGRESS: [],
        Status.DONE: [],
        Status.CANCELLED: []
    }
    
    for todo in todos:
        todos_by_status[todo.status].append(todo)
    
    # Generate kanban columns HTML
    status_config = {
        Status.OPEN: {"title": "To Do", "class": "open"},
        Status.IN_PROGRESS: {"title": "In Progress", "class": "in-progress"},
        Status.DONE: {"title": "Done", "class": "done"},
        Status.CANCELLED: {"title": "Cancelled", "class": "cancelled"}
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
                    tag_class = f"tag-{tag.lower()}" if tag.lower() in [
                        'backend', 'frontend', 'security', 'feature', 'bugfix', 
                        'enhancement', 'testing', 'docs', 'api', 'ui', 'database', 
                        'performance', 'refactor'
                    ] else ""
                    tag_elements.append(f'<span class="tag {tag_class}">{tag}</span>')
                if len(tags) > 5:
                    tag_elements.append(f'<span class="tag">+{len(tags)-5}</span>')
                tags_html = f'<div class="card-tags">{"".join(tag_elements)}</div>'
            
            due_date_html = ""
            if todo.due_date:
                due_date_html = f'<div class="due-date">Due: {todo.due_date}</div>'
            
            todo_cards += f'''
            <div class="todo-card priority-{todo.priority}" data-todo-id="{todo.id}">
                <div class="card-header">
                    <div class="card-title">{todo.description}</div>
                    <div class="card-id">#{todo.id}</div>
                </div>
                {tags_html}
                {due_date_html}
                <div class="card-footer">
                    <div class="priority-indicator">
                        <div class="priority-dot {todo.priority}"></div>
                        <span>{todo.priority.title()} Priority</span>
                    </div>
                    <div class="card-actions">
                        <button class="btn btn-sm" hx-delete="/todos/{todo.id}" hx-target="#kanban-board" hx-swap="innerHTML" hx-confirm="Delete this todo?">Delete</button>
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
            <div class="todo-list" data-status="{status}">
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
    session: Session = Depends(get_session)
):
    """Create a new todo"""
    due_date_obj = None
    if due_date:
        try:
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    todo = Todo(
        description=description,
        priority=priority,
        tags=tags if tags else None,
        due_date=due_date_obj
    )
    
    session.add(todo)
    session.commit()
    
    # Return updated kanban board HTML
    return generate_kanban_html(session)

@app.put("/todos/{todo_id}/status")
async def update_todo_status(
    todo_id: int,
    status: Status = Form(...),
    session: Session = Depends(get_session)
):
    """Update todo status (for drag and drop)"""
    todo = session.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    todo.status = status
    todo.updated_at = datetime.utcnow()
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
    
    session.delete(todo)
    session.commit()
    
    # Return updated kanban board HTML
    return generate_kanban_html(session)

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
    
    print(f"Database: {database_file}")
    return database_url

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Todo Kanban Web Interface")
    parser.add_argument(
        "--project-dir",
        type=str,
        help="Project directory containing todo.db"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    
    args = parser.parse_args()
    
    # Setup database
    setup_database(args.project_dir)
    
    print(f"🚀 Starting Todo Kanban Board at http://{args.host}:{args.port}")
    print("   Press Ctrl+C to stop")
    
    # Run the server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )

if __name__ == "__main__":
    main()