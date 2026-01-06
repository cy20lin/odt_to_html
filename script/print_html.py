# import argparse
# from bs4 import BeautifulSoup, NavigableString, Tag
# from rich.tree import Tree
# from rich.console import Console

# def build_rich_tree(soup_node, rich_tree_node):
#     """Recursively build a rich Tree from a BeautifulSoup node."""
#     for child in soup_node.children:
#         if isinstance(child, NavigableString):
#             content = str(child).strip()
#             if content:
#                 # Add text content as a leaf node
#                 rich_tree_node.add(f"[dim]\"{content[:50]}...\"[/dim]")
#         elif isinstance(child, Tag):
#             # Create a new branch for a tag
#             tag_name = child.name
#             attrs = ' '.join([f'{k}="{v}"' for k, v in child.attrs.items()])
#             label = f"[bold cyan]<{tag_name}[/bold cyan] [yellow]{attrs}[/yellow][bold cyan]>[/bold cyan]"
#             new_branch = rich_tree_node.add(label)
#             build_rich_tree(child, new_branch)

# def main():
#     """Main function to parse CLI arguments and print the HTML tree."""
#     parser = argparse.ArgumentParser(description="Print a hierarchical tree of an HTML file.")
#     parser.add_argument("input_path", type=str, help="Path to the input HTML file.")
#     args = parser.parse_args()

#     try:
#         with open(args.input_path, 'r', encoding='utf-8') as f:
#             html_content = f.read()
        
#         soup = BeautifulSoup(html_content, 'html.parser')
        
#         console = Console()
#         if soup.html:
#             # Start the tree from the <html> tag
#             html_attrs = ' '.join([f'{k}="{v}"' for k, v in soup.html.attrs.items()])
#             root_label = f"[bold cyan]<html>[/bold cyan] [yellow]{html_attrs}[/yellow]" if html_attrs else "[bold cyan]<html>[/bold cyan]"
#             html_tree = Tree(root_label)
#             build_rich_tree(soup.html, html_tree)
#             console.print(html_tree)
#         else:
#             console.print("[bold red]Error: Could not find <html> tag in the document.[/bold red]")

#     except FileNotFoundError:
#         console.print(f"[bold red]Error: The file '{args.input_path}' was not found.[/bold red]")
#     except Exception as e:
#         console.print(f"[bold red]An error occurred: {e}[/bold red]")

# if __name__ == "__main__":
#     main()

import argparse
from bs4 import BeautifulSoup, NavigableString, Tag
from rich.tree import Tree
from rich.console import Console

def is_base64_data(content: str) -> bool:
    """Check if the string looks like embedded base64 data."""
    return content.startswith("data:") and "base64," in content

def build_rich_tree(soup_node, rich_tree_node):
    """Recursively build a rich Tree from a BeautifulSoup node."""
    for child in soup_node.children:
        if isinstance(child, NavigableString):
            content = str(child).strip()
            if content:
                # Skip long base64-like strings
                if len(content) > 100 and "base64" in content:
                    continue
                rich_tree_node.add(f"[dim]\"{content[:50]}...\"[/dim]")
        elif isinstance(child, Tag):
            # Filter attributes to avoid printing base64 blobs
            attrs_list = []
            for k, v in child.attrs.items():
                if isinstance(v, str) and is_base64_data(v):
                    attrs_list.append(f'{k}="[base64 data omitted]"')
                else:
                    attrs_list.append(f'{k}="{v}"')
            attrs = ' '.join(attrs_list)

            tag_name = child.name
            label = f"[bold cyan]<{tag_name}[/bold cyan] [yellow]{attrs}[/yellow][bold cyan]>[/bold cyan]"
            new_branch = rich_tree_node.add(label)
            build_rich_tree(child, new_branch)

def main():
    """Main function to parse CLI arguments and print the HTML tree."""
    parser = argparse.ArgumentParser(description="Print a hierarchical tree of an HTML file.")
    parser.add_argument("input_path", type=str, help="Path to the input HTML file.")
    args = parser.parse_args()

    try:
        with open(args.input_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        console = Console()
        if soup.html:
            # Start the tree from the <html> tag
            html_attrs = ' '.join([f'{k}="{v}"' for k, v in soup.html.attrs.items()])
            root_label = f"[bold cyan]<html>[/bold cyan] [yellow]{html_attrs}[/yellow]" if html_attrs else "[bold cyan]<html>[/bold cyan]"
            html_tree = Tree(root_label)
            build_rich_tree(soup.html, html_tree)
            console.print(html_tree)
        else:
            console.print("[bold red]Error: Could not find <html> tag in the document.[/bold red]")

    except FileNotFoundError:
        console.print(f"[bold red]Error: The file '{args.input_path}' was not found.[/bold red]")
    except Exception as e:
        console.print(f"[bold red]An error occurred: {e}[/bold red]")

if __name__ == "__main__":
    main()

