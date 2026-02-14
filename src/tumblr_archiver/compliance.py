"""
Compliance utilities for ensuring legal and ethical usage.

This module provides functions to display terms of service notices,
check robots.txt compliance, and validate that usage follows
ethical and legal guidelines.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

try:
    from .http_client import AsyncHTTPClient
except ImportError:
    AsyncHTTPClient = None

logger = logging.getLogger(__name__)


class ComplianceError(Exception):
    """Base exception for compliance-related errors."""
    pass


class TermsNotAcceptedError(ComplianceError):
    """Raised when user has not accepted terms of use."""
    pass


class RobotsTxtViolationError(ComplianceError):
    """Raised when an action would violate robots.txt."""
    pass


def show_terms_notice() -> None:
    """
    Display terms of service notice on first run.
    
    Shows important legal and ethical notices to the user,
    including copyright responsibilities, rate limits, and
    terms of service compliance.
    
    This should be called before any archiving operations begin.
    """
    notice = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    TUMBLR ARCHIVER - TERMS OF USE                          ║
╚════════════════════════════════════════════════════════════════════════════╝

IMPORTANT LEGAL NOTICE:

By using this tool, you agree to the following terms:

1. COPYRIGHT COMPLIANCE
   - You may only archive content you have permission to access
   - Respect all copyright and intellectual property rights
   - Downloaded content is for personal backup purposes only
   - Do not redistribute archived content without permission

2. TUMBLR TERMS OF SERVICE
   - You must comply with Tumblr's Terms of Service
   - You are responsible for ensuring your usage is permitted
   - This tool is for personal archiving and backup only
   - Commercial use is prohibited without proper authorization

3. RATE LIMITS & RESPECTFUL USE
   - This tool implements rate limiting to be respectful
   - Do not attempt to circumvent rate limits
   - Excessive requests may result in IP blocks
   - Use reasonable delays between requests

4. PRIVACY & DATA PROTECTION
   - Respect the privacy of content creators
   - Handle archived data responsibly
   - Do not share private or sensitive content
   - Comply with applicable data protection laws (GDPR, CCPA, etc.)

5. DISCLAIMER
   - This tool is provided "AS IS" without warranty
   - You use this tool at your own risk
   - The developers are not responsible for misuse
   - You are solely responsible for compliance with all laws

6. WAYBACK MACHINE USAGE
   - When using Internet Archive features, you agree to their Terms of Use
   - Archived content from Wayback Machine is subject to their policies
   - Respect the Internet Archive's acceptable use policies

For full terms, see TERMS_OF_USE.md in the project root.

╔════════════════════════════════════════════════════════════════════════════╗
║ By continuing, you acknowledge that you have read, understood, and agree   ║
║ to comply with these terms.                                                ║
╚════════════════════════════════════════════════════════════════════════════╝
"""
    print(notice)
    logger.info("Terms of use notice displayed to user")


def check_terms_acceptance(config_dir: Optional[Path] = None) -> bool:
    """
    Check if user has previously accepted terms.
    
    Args:
        config_dir: Directory where acceptance marker is stored
        
    Returns:
        True if terms have been accepted, False otherwise
    """
    if config_dir is None:
        config_dir = Path.home() / '.tumblr_archiver'
    
    acceptance_file = config_dir / '.terms_accepted'
    return acceptance_file.exists()


def record_terms_acceptance(config_dir: Optional[Path] = None) -> None:
    """
    Record that user has accepted terms.
    
    Args:
        config_dir: Directory where acceptance marker should be stored
    """
    if config_dir is None:
        config_dir = Path.home() / '.tumblr_archiver'
    
    config_dir.mkdir(parents=True, exist_ok=True)
    acceptance_file = config_dir / '.terms_accepted'
    acceptance_file.touch()
    logger.info("Terms acceptance recorded")


def prompt_terms_acceptance(config_dir: Optional[Path] = None) -> bool:
    """
    Show terms and prompt user to accept.
    
    Args:
        config_dir: Directory where acceptance marker should be stored
        
    Returns:
        True if user accepted, False otherwise
    """
    show_terms_notice()
    
    try:
        response = input("\nDo you accept these terms? (yes/no): ").strip().lower()
        
        if response in ['yes', 'y']:
            record_terms_acceptance(config_dir)
            print("\n✓ Terms accepted. Proceeding...\n")
            logger.info("User accepted terms of use")
            return True
        else:
            print("\n✗ Terms not accepted. Exiting...\n")
            logger.info("User declined terms of use")
            return False
            
    except (KeyboardInterrupt, EOFError):
        print("\n\n✗ Terms not accepted. Exiting...\n")
        logger.info("Terms acceptance interrupted by user")
        return False


async def check_robots_txt(
    domain: str,
    user_agent: str = "TumblrArchiver/1.0",
    timeout: float = 10.0
) -> dict[str, any]:
    """
    Check robots.txt for the given domain.
    
    This is an optional compliance feature that checks if the domain
    has a robots.txt file and what rules it specifies.
    
    Args:
        domain: The domain to check (e.g., "example.tumblr.com")
        user_agent: The user agent string to check rules for
        timeout: Timeout for the HTTP request
        
    Returns:
        Dictionary with robots.txt information:
        - 'exists': Whether robots.txt exists
        - 'content': Raw robots.txt content (if exists)
        - 'disallowed_paths': List of disallowed paths for the user agent
        - 'crawl_delay': Crawl delay in seconds (if specified)
        
    Examples:
        >>> result = await check_robots_txt("example.tumblr.com")
        >>> result['exists']
        True
    """
    # Ensure domain has scheme
    if not domain.startswith(('http://', 'https://')):
        domain = f'https://{domain}'
    
    parsed = urlparse(domain)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    result = {
        'exists': False,
        'content': None,
        'disallowed_paths': [],
        'crawl_delay': None,
        'user_agent': user_agent
    }
    
    if AsyncHTTPClient is None:
        logger.warning("AsyncHTTPClient not available, skipping robots.txt check")
        return result
    
    try:
        async with AsyncHTTPClient(timeout=timeout) as client:
            try:
                response_text = await client.fetch_text(robots_url)
                
                result['exists'] = True
                result['content'] = response_text
                
                # Parse robots.txt (basic parsing)
                current_user_agent = None
                applies_to_us = False
                
                for line in response_text.split('\n'):
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse directives
                    if ':' in line:
                        directive, value = line.split(':', 1)
                        directive = directive.strip().lower()
                        value = value.strip()
                        
                        if directive == 'user-agent':
                            current_user_agent = value
                            # Check if this applies to our user agent
                            applies_to_us = (
                                value == '*' or
                                value.lower() in user_agent.lower()
                            )
                        
                        elif applies_to_us:
                            if directive == 'disallow':
                                if value:
                                    result['disallowed_paths'].append(value)
                            
                            elif directive == 'crawl-delay':
                                try:
                                    result['crawl_delay'] = float(value)
                                except ValueError:
                                    pass
                
                logger.info(f"robots.txt checked for {domain}: {len(result['disallowed_paths'])} disallowed paths")
            except Exception as fetch_error:
                logger.debug(f"Could not fetch robots.txt for {domain}: {fetch_error}")
                
    except Exception as e:
        logger.debug(f"Error checking robots.txt for {domain}: {e}")
    
    return result


def is_path_allowed_by_robots(path: str, disallowed_paths: list[str]) -> bool:
    """
    Check if a path is allowed according to robots.txt rules.
    
    Args:
        path: The URL path to check
        disallowed_paths: List of disallowed paths from robots.txt
        
    Returns:
        True if the path is allowed, False if disallowed
        
    Examples:
        >>> is_path_allowed_by_robots("/post/123", ["/admin", "/private"])
        True
        >>> is_path_allowed_by_robots("/admin/settings", ["/admin"])
        False
    """
    if not disallowed_paths:
        return True
    
    for disallowed in disallowed_paths:
        # Simple prefix matching (robots.txt disallow rules)
        if path.startswith(disallowed):
            return False
    
    return True


def is_compliant_usage(config: dict) -> tuple[bool, list[str]]:
    """
    Validate that the configuration represents compliant usage.
    
    Checks for:
    - Reasonable rate limits
    - Appropriate concurrency
    - No suspicious patterns
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        Tuple of (is_compliant, list_of_warnings)
        
    Examples:
        >>> config = {'rate_limit': 1.0, 'max_workers': 3}
        >>> is_compliant, warnings = is_compliant_usage(config)
        >>> is_compliant
        True
    """
    warnings = []
    is_compliant = True
    
    # Check rate limit
    rate_limit = config.get('rate_limit', 1.0)
    if rate_limit < 0.5:
        warnings.append(
            f"Rate limit of {rate_limit}s is very aggressive. "
            "Consider using at least 0.5s to be respectful."
        )
        # Still compliant but warned
    
    if rate_limit < 0.1:
        warnings.append(
            "Rate limit below 0.1s may result in IP blocks. "
            "This is not recommended."
        )
        is_compliant = False
    
    # Check concurrency
    max_workers = config.get('max_workers', 3)
    if max_workers > 10:
        warnings.append(
            f"High concurrency ({max_workers} workers) may overwhelm servers. "
            "Consider reducing to 5 or fewer workers."
        )
        # Still compliant but warned
    
    if max_workers > 20:
        warnings.append(
            "Excessive concurrency may be considered abuse. "
            "Please reduce worker count."
        )
        is_compliant = False
    
    # Check timeout
    timeout = config.get('timeout', 30.0)
    if timeout < 5.0:
        warnings.append(
            f"Timeout of {timeout}s may be too short and cause failures. "
            "Consider using at least 10s."
        )
    
    # Log compliance check
    if is_compliant:
        if warnings:
            logger.warning(f"Usage is compliant but has warnings: {warnings}")
        else:
            logger.info("Usage configuration validated as compliant")
    else:
        logger.error(f"Usage configuration is NOT compliant: {warnings}")
    
    return is_compliant, warnings


def log_compliance_event(event_type: str, details: dict) -> None:
    """
    Log a compliance-related event.
    
    Args:
        event_type: Type of compliance event (e.g., 'terms_accepted', 'robots_checked')
        details: Additional details about the event
    """
    logger.info(f"Compliance event: {event_type}", extra={
        'event_type': event_type,
        'details': details
    })


def get_ethical_usage_guidelines() -> str:
    """
    Get ethical usage guidelines as a formatted string.
    
    Returns:
        Formatted string with ethical guidelines
    """
    return """
Ethical Usage Guidelines:

1. Respect Content Creators
   - Only archive content you have permission to access
   - Respect copyright and attribution
   - Don't redistribute without permission

2. Be Respectful of Services
   - Use reasonable rate limits (at least 0.5s between requests)
   - Don't overwhelm servers with excessive concurrent requests
   - Accept when content is unavailable

3. Privacy Considerations
   - Handle private content with care
   - Don't share sensitive information
   - Respect content removal requests

4. Legal Compliance
   - Follow all applicable laws and regulations
   - Comply with terms of service
   - Respect robots.txt when specified

5. Responsible Use
   - Use for personal backup and archiving only
   - Don't use for commercial purposes without authorization
   - Report bugs and security issues responsibly
"""
