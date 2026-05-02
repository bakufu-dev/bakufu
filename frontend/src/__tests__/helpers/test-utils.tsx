import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type RenderOptions, render } from "@testing-library/react";
import type React from "react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

interface WrapperOptions {
  initialEntries?: string[];
  queryClient?: QueryClient;
}

export function createWrapper(opts: WrapperOptions = {}) {
  const { initialEntries = ["/"], queryClient = createTestQueryClient() } = opts;

  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
    </QueryClientProvider>
  );

  return { Wrapper, queryClient };
}

export function renderWithProviders(
  ui: ReactElement,
  opts: WrapperOptions & Omit<RenderOptions, "wrapper"> = {},
) {
  const { initialEntries, queryClient, ...renderOptions } = opts;
  const { Wrapper, queryClient: qc } = createWrapper({ initialEntries, queryClient });

  const result = render(ui, { wrapper: Wrapper, ...renderOptions });
  return { ...result, queryClient: qc };
}
