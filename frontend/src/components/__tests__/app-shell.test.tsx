/**
 * @jest-environment jsdom
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AppShell from '../app-shell'

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
  }),
}))

// Mock Supabase
jest.mock('../../lib/supabase-browser', () => ({
  supabase: {
    auth: {
      getUser: jest.fn().mockResolvedValue({
        data: { user: { email: 'test@example.com', user_metadata: { full_name: 'Test User' } } },
      }),
      getSession: jest.fn().mockResolvedValue({
        data: { session: { access_token: 'mock-token' } },
      }),
      signOut: jest.fn().mockResolvedValue({}),
      onAuthStateChange: jest.fn(() => ({
        data: { subscription: { unsubscribe: jest.fn() } },
      })),
    },
  },
}))

// Mock avatar resolver
jest.mock('../../lib/avatar', () => ({
  resolveAvatarUrl: jest.fn().mockResolvedValue('https://example.com/avatar.jpg'),
}))

describe('AppShell', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
    // Mock window object
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: jest.fn((key) => {
          if (key === 'baxel:plan-label') return 'Starter'
          return null
        }),
        setItem: jest.fn(),
        removeItem: jest.fn(),
        clear: jest.fn(),
      },
      writable: true,
    })
  })

  it('renders without crashing', () => {
    render(<AppShell>Test Content</AppShell>)
    expect(screen.getByText('Test Content')).toBeInTheDocument()
  })

  it('displays Baxel logo and branding', () => {
    render(<AppShell>Test Content</AppShell>)
    expect(screen.getByText('Baxel')).toBeInTheDocument()
  })

  it('displays navigation links', () => {
    render(<AppShell>Test Content</AppShell>)
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Projects')).toBeInTheDocument()
    expect(screen.getByText('Pipelines')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('displays plan badge', () => {
    render(<AppShell>Test Content</AppShell>)
    expect(screen.getByText('Starter')).toBeInTheDocument()
  })

  it('opens profile menu on button click', async () => {
    render(<AppShell>Test Content</AppShell>)

    const profileButton = screen.getByText('Profile')
    fireEvent.click(profileButton)

    await waitFor(() => {
      expect(screen.getByText('Profile settings')).toBeInTheDocument()
    })
  })

  it('closes profile menu when clicking outside', async () => {
    render(<AppShell>Test Content</AppShell>)

    const profileButton = screen.getByText('Profile')
    fireEvent.click(profileButton)

    await waitFor(() => {
      expect(screen.getByText('Profile settings')).toBeInTheDocument()
    })

    // Click outside the menu
    fireEvent.mouseDown(document.body)

    await waitFor(() => {
      expect(screen.queryByText('Profile settings')).not.toBeInTheDocument()
    })
  })

  it('toggles mobile navigation', () => {
    render(<AppShell>Test Content</AppShell>)

    const mobileMenuButton = screen.getByRole('button', { name: /toggle navigation/i })
    fireEvent.click(mobileMenuButton)

    expect(screen.getByText('Navigation')).toBeInTheDocument()
  })

  it('displays user display name', async () => {
    render(<AppShell>Test Content</AppShell>)

    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument()
    })
  })

  it('shows logout confirmation dialog', async () => {
    render(<AppShell>Test Content</AppShell>)

    const profileButton = screen.getByText('Profile')
    fireEvent.click(profileButton)

    await waitFor(() => {
      expect(screen.getByText('Profile settings')).toBeInTheDocument()
    })

    const logoutButton = screen.getByText('Logout')
    fireEvent.click(logoutButton)

    await waitFor(() => {
      expect(screen.getByText('Confirm logout')).toBeInTheDocument()
    })
  })
})