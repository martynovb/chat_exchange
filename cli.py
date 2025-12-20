#!/usr/bin/env python3
"""
Interactive CLI for exporting AI chats to PromptShare.
Uses Rich library for beautiful terminal UI.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

# Add project root to Python path so imports work when running script directly
project_root = pathlib.Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.domain.claude_chat_finder import ClaudeChatFinder
from src.domain.copilot_chat_finder import CopilotChatFinder
from src.domain.cursor_chats_finder import CursorChatFinder

console = Console()


def get_finder(finder_type: str):
    """Get the appropriate finder instance based on type.
    
    Args:
        finder_type: One of 'cursor', 'claude_code', 'ms_copilot'
        
    Returns:
        Finder instance
        
    Raises:
        ValueError: If finder_type is invalid
    """
    finder_type = finder_type.lower()
    
    if finder_type == "cursor":
        return CursorChatFinder()
    elif finder_type == "claude_code":
        return ClaudeChatFinder()
    elif finder_type == "ms_copilot":
        return CopilotChatFinder()
    else:
        raise ValueError(f"Unknown finder type: {finder_type}")


def show_intro():
    """Display the intro banner."""
    console.print()
    intro_text = Text(" Export AI chat to PromptShare ", style="bold reverse")
    console.print(Panel(intro_text, border_style="blue"))


def check_authentication() -> str:
    """Check authentication and prompt for token.
    
    Returns:
        Auth token string
    """
    with console.status("[bold blue]Checking authentication...", spinner="dots"):
        time.sleep(1)  # Simulate auth check
    
    token = Prompt.ask(
        "\n[bold]Please enter your auth token[/bold]",
        default="",
        console=console
    )
    
    if not token:
        console.print("[yellow]No token provided. Continuing without authentication...[/yellow]")
    
    return token


def select_chat_source() -> str:
    """Prompt user to select chat source.
    
    Returns:
        Selected finder type: 'cursor', 'claude_code', or 'ms_copilot'
    """
    console.print("\n[bold]Choose from where you want to export chat from:[/bold]")
    
    options = [
        ("1", "Cursor", "cursor"),
        ("2", "Claude Code", "claude_code"),
        ("3", "MS Copilot", "ms_copilot"),
    ]
    
    # Display options
    table = Table(show_header=False, box=None, padding=(0, 2))
    for key, label, _ in options:
        table.add_row(f"[cyan]{key}[/cyan]", label)
    
    console.print(table)
    
    while True:
        choice = Prompt.ask("\n[bold]Select option[/bold]", default="1")
        
        for key, _, finder_type in options:
            if choice == key or choice.lower() == finder_type.lower():
                return finder_type
        
        console.print("[red]Invalid option. Please try again.[/red]")


def select_conversation(finder) -> Optional[dict]:
    """List and select a conversation with pagination support.
    
    Args:
        finder: Chat finder instance
        
    Returns:
        Selected conversation metadata dict, or None if cancelled
    """
    console.print("\n[bold]Loading conversations...[/bold]")
    
    with console.status("[bold blue]Scanning for chats...", spinner="dots"):
        try:
            metadata_list = finder.get_chat_metadata_list()
        except Exception as e:
            console.print(f"[red]Error loading conversations: {e}[/red]")
            return None
    
    if not metadata_list:
        console.print("[yellow]No conversations found.[/yellow]")
        return None
    
    # Sort by date (newest first)
    # Date format is "YYYY-MM-DD", so we can sort as strings, but handle missing dates
    def get_sort_key(chat: dict) -> str:
        """Get sort key for chat - newest dates first."""
        date_str = chat.get("date", "")
        if not date_str or date_str == "Unknown":
            # Put chats without dates at the end
            return "0000-00-00"
        return date_str
    
    metadata_list.sort(key=get_sort_key, reverse=True)
    
    # Pagination settings
    page_size = 50
    total_chats = len(metadata_list)
    total_pages = (total_chats + page_size - 1) // page_size
    current_page = 1
    
    def display_page(page: int) -> None:
        """Display a specific page of conversations."""
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_chats)
        page_chats = metadata_list[start_idx:end_idx]
        
        console.print(f"\n[bold]Found {total_chats} conversations:[/bold]")
        console.print(f"[dim]Page {page} of {total_pages} (showing {start_idx + 1}-{end_idx} of {total_chats})[/dim]\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Title", style="white", width=60)
        table.add_column("Date", style="green", width=12)
        # ID column width set to 18 to display full 16-character hex IDs (matching finder.py output)
        table.add_column("ID", style="dim", width=18)
        
        for idx, chat in enumerate(page_chats, start=start_idx + 1):
            title = chat.get("title", "Untitled")
            if len(title) > 55:
                title = title[:52] + "..."
            table.add_row(
                str(idx),
                title,
                chat.get("date", "Unknown"),
                chat.get("id", "")  # Show full ID, not truncated
            )
        
        console.print(table)
        
        # Show pagination hints if there are multiple pages
        if total_pages > 1:
            pagination_hints = []
            if page > 1:
                pagination_hints.append("[cyan]'p'[/cyan] or [cyan]'prev'[/cyan] for previous page")
            if page < total_pages:
                pagination_hints.append("[cyan]'n'[/cyan] or [cyan]'next'[/cyan] for next page")
            if pagination_hints:
                console.print(f"\n[dim]{' | '.join(pagination_hints)}[/dim]")
    
    # Display first page
    display_page(current_page)
    
    # Main selection loop with pagination
    while True:
        try:
            choice = Prompt.ask(
                f"\n[bold]Choose conversation (1-{total_chats}) or navigate pages[/bold]",
                default=""
            )
            
            choice_lower = choice.lower().strip()
            
            # Handle pagination commands
            if choice_lower in ['n', 'next']:
                if current_page < total_pages:
                    current_page += 1
                    display_page(current_page)
                else:
                    console.print("[yellow]Already on the last page[/yellow]")
                continue
            elif choice_lower in ['p', 'prev', 'previous']:
                if current_page > 1:
                    current_page -= 1
                    display_page(current_page)
                else:
                    console.print("[yellow]Already on the first page[/yellow]")
                continue
            elif choice_lower.startswith('page '):
                try:
                    page_num = int(choice_lower.replace('page ', ''))
                    if 1 <= page_num <= total_pages:
                        current_page = page_num
                        display_page(current_page)
                    else:
                        console.print(f"[red]Please enter a page number between 1 and {total_pages}[/red]")
                except ValueError:
                    console.print("[red]Invalid page number format. Use 'page N' where N is the page number[/red]")
                continue
            
            # Handle conversation selection
            if not choice:
                continue
                
            idx = int(choice) - 1
            if 0 <= idx < total_chats:
                return metadata_list[idx]
            else:
                console.print(f"[red]Please enter a number between 1 and {total_chats}[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number, or use 'n'/'next'/'p'/'prev' for pagination[/red]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled[/yellow]")
            return None


def export_conversation(finder, conversation_metadata: dict, auth_token: str) -> bool:
    """Export the selected conversation.
    
    Args:
        finder: Chat finder instance
        conversation_metadata: Selected conversation metadata
        auth_token: Authentication token (for future use)
        
    Returns:
        True if export successful, False otherwise
    """
    chat_id = conversation_metadata.get("id")
    title = conversation_metadata.get("title", "Untitled")
    
    console.print(f"\n[bold]Exporting conversation:[/bold] [cyan]{title}[/cyan]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[bold blue]Exporting the conversation...", total=None)
        
        try:
            # Parse the full chat
            chat_data = finder.parse_chat_by_id(chat_id)
            
            # Save to results folder
            output_path = finder._get_default_output_path(
                f"{finder._finder_type}_chat_{chat_id[:8]}.json"
            )
            
            output_path.write_text(
                json.dumps(chat_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            
            progress.update(task, completed=True)
            time.sleep(0.5)  # Brief pause for UX
            
        except Exception as e:
            console.print(f"[red]Error exporting conversation: {e}[/red]")
            return False
    
    console.print("[bold green]✓ Export completed successfully![/bold green]")
    console.print(f"\n[dim]Saved to: {output_path}[/dim]")
    
    # For now, just show the local path. In the future, this could upload to PromptShare
    # if auth_token:
    #     console.print(f"\n[bold]Your AI conversation is available at:[/bold] [cyan]goo.gle/org/team/my-cool-ai-chat/[/cyan]")
    
    return True


def show_outro():
    """Display the outro message."""
    console.print()
    outro_text = Text("Thank you for using Chat Exchange CLI!", style="bold green")
    console.print(Panel(outro_text, border_style="green"))


def main() -> int:
    """Main CLI entry point.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Show intro
        show_intro()
        
        # Check authentication
        auth_token = check_authentication()
        
        # Select chat source
        finder_type = select_chat_source()
        
        try:
            finder = get_finder(finder_type)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return 1
        
        # Select conversation
        conversation = select_conversation(finder)
        if not conversation:
            console.print("[yellow]No conversation selected. Exiting.[/yellow]")
            return 0
        
        # Export conversation
        success = export_conversation(finder, conversation, auth_token)
        
        if success:
            show_outro()
            return 0
        else:
            return 1
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        return 0
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())

